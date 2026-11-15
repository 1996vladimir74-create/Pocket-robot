import SwiftUI
import CoreBluetooth
import BackgroundTasks
import UIKit
import Combine

private let serviceID = CBUUID(string: "12345678-1234-5678-1234-56789abcdef0")
private let rxID = CBUUID(string: "12345678-1234-5678-1234-56789abcdef1")
private let refreshID = "com.pocketrobot.phone.refresh"

@main
struct PocketRobotApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @Environment(\.scenePhase) private var scenePhase
    @StateObject private var bridge = PhoneBridge.shared

    var body: some Scene {
        WindowGroup {
            ContentView(bridge: bridge)
                .onChange(of: scenePhase) { _, phase in
                    if phase == .active { bridge.startForegroundPolling() }
                    else { bridge.stopForegroundPolling() }
                }
        }
    }
}

final class AppDelegate: NSObject, UIApplicationDelegate {
    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        BGTaskScheduler.shared.register(forTaskWithIdentifier: refreshID, using: nil) { task in
            guard let task = task as? BGAppRefreshTask else { return }
            PhoneBridge.shared.performBackgroundRefresh(task: task)
        }
        PhoneBridge.shared.startBluetooth()
        PhoneBridge.shared.scheduleRefresh()
        return true
    }
}

@MainActor
final class PhoneBridge: NSObject, ObservableObject {
    static let shared = PhoneBridge()
    @Published var status = "Ожидание Bluetooth"
    @Published var serverURL = UserDefaults.standard.string(forKey: "serverURL") ?? "http://100.x.y.z:8080"
    @Published var phoneToken = UserDefaults.standard.string(forKey: "phoneToken") ?? ""
    @Published var isConnected = false

    private var central: CBCentralManager!
    private var robot: CBPeripheral?
    private var rxCharacteristic: CBCharacteristic?
    private var pollTask: Task<Void, Never>?
    private var isPolling = false
    private var pendingMessageID: Int?
    private var pendingText: String?
    private var pendingChunks: [Data] = []
    private var chunkIndex = 0
    private var sequence: UInt8 = 0

    override init() {
        super.init()
        central = CBCentralManager(delegate: self, queue: nil,
            options: [CBCentralManagerOptionRestoreIdentifierKey: "com.pocketrobot.central"])
    }

    func startBluetooth() {
        if central.state == .poweredOn { scan() }
    }

    private func scan() {
        guard central.state == .poweredOn, robot == nil else { return }
        status = "Поиск Pocket Robot"
        central.scanForPeripherals(withServices: [serviceID],
            options: [CBCentralManagerScanOptionAllowDuplicatesKey: false])
    }

    func startForegroundPolling() {
        stopForegroundPolling()
        pollTask = Task {
            while !Task.isCancelled {
                await pollOnce()
                try? await Task.sleep(for: .seconds(12))
            }
        }
    }

    func stopForegroundPolling() {
        pollTask?.cancel()
        pollTask = nil
    }

    func scheduleRefresh() {
        let request = BGAppRefreshTaskRequest(identifier: refreshID)
        request.earliestBeginDate = Date(timeIntervalSinceNow: 15 * 60)
        try? BGTaskScheduler.shared.submit(request)
    }

    func performBackgroundRefresh(task: BGAppRefreshTask) {
        scheduleRefresh()
        let work = Task {
            await pollOnce()
            task.setTaskCompleted(success: true)
        }
        task.expirationHandler = { work.cancel() }
    }

    func saveSettings() {
        UserDefaults.standard.set(serverURL.trimmingCharacters(in: .whitespacesAndNewlines), forKey: "serverURL")
        UserDefaults.standard.set(phoneToken, forKey: "phoneToken")
        status = "Настройки сохранены"
    }

    func pollOnce() async {
        guard !isPolling, !phoneToken.isEmpty,
              let base = URL(string: serverURL.trimmingCharacters(in: CharacterSet(charactersIn: "/"))) else { return }
        isPolling = true
        defer { isPolling = false }
        do {
            var request = URLRequest(url: base.appending(path: "/api/phone/messages/next"))
            request.httpMethod = "GET"
            request.setValue("Bearer " + phoneToken, forHTTPHeaderField: "Authorization")
            request.timeoutInterval = 8
            let (data, response) = try await URLSession.shared.data(for: request)
            guard (response as? HTTPURLResponse)?.statusCode == 200 else {
                status = "Ошибка сервера"
                return
            }
            let envelope = try JSONDecoder().decode(PhoneQueueResponse.self, from: data)
            guard let message = envelope.message else { return }
            pendingMessageID = message.id
            pendingText = message.text
            if robot == nil { scan() }
            sendPendingIfReady()
            status = "Получено сообщение: ожидаю BLE"
        } catch {
            status = "Нет связи с сервером"
        }
    }

    private func sendPendingIfReady() {
        guard let peripheral = robot, let characteristic = rxCharacteristic,
              let text = pendingText, peripheral.state == .connected else { return }
        if pendingChunks.isEmpty {
            let bytes = Array(text.utf8)
            let payloadLimit = max(1, min(13, peripheral.maximumWriteValueLength(for: .withResponse) - 7))
            let count = max(1, (bytes.count + payloadLimit - 1) / payloadLimit)
            sequence &+= 1
            pendingChunks = (0..<count).map { index in
                let start = index * payloadLimit
                let end = min(bytes.count, start + payloadLimit)
                var packet = Data(String(format: "P%02X%02X%02X", sequence, index, count).utf8)
                if start < end { packet.append(contentsOf: bytes[start..<end]) }
                return packet
            }
            chunkIndex = 0
        }
        guard chunkIndex < pendingChunks.count else { return }
        peripheral.writeValue(pendingChunks[chunkIndex], for: characteristic, type: .withResponse)
    }

    private func acknowledgeOnServer(_ id: Int) async {
        guard let base = URL(string: serverURL.trimmingCharacters(in: CharacterSet(charactersIn: "/"))) else { return }
        var request = URLRequest(url: base.appending(path: "/api/phone/messages/\(id)/ack"))
        request.httpMethod = "POST"
        request.setValue("Bearer " + phoneToken, forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = Data("{}".utf8)
        _ = try? await URLSession.shared.data(for: request)
    }
}

extension PhoneBridge: CBCentralManagerDelegate {
    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        if central.state == .poweredOn { scan() }
        else { status = "Bluetooth недоступен" }
    }

    func centralManager(_ central: CBCentralManager, willRestoreState dict: [String: Any]) {
        if let peripherals = dict[CBCentralManagerRestoredStatePeripheralsKey] as? [CBPeripheral],
           let peripheral = peripherals.first {
            robot = peripheral
            peripheral.delegate = self
            if peripheral.state == .connected { peripheral.discoverServices([serviceID]) }
        }
    }

    func centralManager(_ central: CBCentralManager, didDiscover peripheral: CBPeripheral,
                        advertisementData: [String: Any], rssi RSSI: NSNumber) {
        robot = peripheral
        robot?.delegate = self
        central.stopScan()
        central.connect(peripheral)
        status = "Подключение к роботу"
    }

    func centralManager(_ central: CBCentralManager, didConnect peripheral: CBPeripheral) {
        isConnected = true
        status = "Bluetooth подключён"
        peripheral.discoverServices([serviceID])
    }

    func centralManager(_ central: CBCentralManager, didDisconnectPeripheral peripheral: CBPeripheral, error: Error?) {
        isConnected = false
        robot = nil
        rxCharacteristic = nil
        status = "Bluetooth отключён; повторный поиск"
        scan()
    }
}

extension PhoneBridge: CBPeripheralDelegate {
    func peripheral(_ peripheral: CBPeripheral, didDiscoverServices error: Error?) {
        guard error == nil else { return }
        peripheral.services?.filter { $0.uuid == serviceID }.forEach {
            peripheral.discoverCharacteristics([rxID], for: $0)
        }
    }

    func peripheral(_ peripheral: CBPeripheral, didDiscoverCharacteristicsFor service: CBService, error: Error?) {
        guard error == nil else { return }
        rxCharacteristic = service.characteristics?.first { $0.uuid == rxID }
        sendPendingIfReady()
    }

    func peripheral(_ peripheral: CBPeripheral, didWriteValueFor characteristic: CBCharacteristic, error: Error?) {
        guard error == nil, let id = pendingMessageID else {
            status = "Ошибка передачи BLE"
            return
        }
        chunkIndex += 1
        if chunkIndex < pendingChunks.count {
            sendPendingIfReady()
            return
        }
        pendingMessageID = nil
        pendingText = nil
        pendingChunks = []
        chunkIndex = 0
        status = "Уведомление доставлено роботу"
        Task { await acknowledgeOnServer(id) }
    }
}

private struct PhoneQueueResponse: Decodable {
    let message: PhoneMessage?
}
private struct PhoneMessage: Decodable {
    let id: Int
    let text: String
}

struct ContentView: View {
    @ObservedObject var bridge: PhoneBridge
    var body: some View {
        NavigationStack {
            Form {
                Section("Сервер Android") {
                    TextField("URL сервера / Tailscale IP", text: $bridge.serverURL)
                        .textInputAutocapitalization(.never).autocorrectionDisabled()
                    SecureField("PHONE_TOKEN", text: $bridge.phoneToken)
                    Button("Сохранить настройки") { bridge.saveSettings() }
                }
                Section("Подключение") {
                    LabeledContent("Bluetooth", value: bridge.isConnected ? "Подключён" : "Нет соединения")
                    Text(bridge.status).font(.footnote)
                    Button("Подключить робота") { bridge.startBluetooth() }
                    Button("Проверить сервер") { Task { await bridge.pollOnce() } }
                }
                Section("Информация") {
                    Text("Оставьте приложение работающим. В фоне iOS может ограничивать периодические запросы; доставка не гарантируется при принудительном закрытии приложения.")
                    Text("Для удалённой связи оба телефона должны быть подключены к одной частной VPN-сети, а сервер Android должен быть запущен.")
                }
            }
            .navigationTitle("Pocket Robot")
        }
    }
}
