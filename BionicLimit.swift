import AppKit

// BionicLimit — native menu bar item showing the remaining Bionic+ weekly limit.
// Reads Bionic's own local cache (~/.lmstudio/apps/bionic/.internal/cloud-account.json).

let cachePath = NSHomeDirectory() + "/.lmstudio/apps/bionic/.internal/cloud-account.json"
let configPath = NSHomeDirectory() + "/Documents/Keanu-Vault/config-bionic-limit.json" // unused, see below
let dashPath = ProcessInfo.processInfo.environment["BIONIC_DASHBOARD_PATH"]
    ?? "/path/to/bionic-usage-dashboard"

func readDict(_ path: String) -> [String: Any]? {
    guard let data = FileManager.default.contents(atPath: path),
          let obj = try? JSONSerialization.jsonObject(with: data),
          let dict = obj as? [String: Any] else { return nil }
    return dict
}

func tokensPerMicrocredit() -> Double {
    // calibration from the dashboard's config.json: weekly budget / 10000 microcredits
    if let cfg = readDict(NSHomeDirectory() + "/.lmstudio/apps/bionic/projects/d49037d8-47f4-5808-9028-c707de117f8f/workspace/bionic-dashboard/config.json"),
       let budget = cfg["weekly_token_budget"] as? Double {
        return budget / 10000.0
    }
    return 18200.0
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
    var timer: Timer?
    var lastInfo: (leftPct: Double, leftTokens: Double, resetHours: Double, generated: String, ageMinutes: Double) =
        (100, 0, 0, "", 0)

    func applicationDidFinishLaunching(_ notification: Notification) {
        item.button?.font = NSFont.monospacedSystemFont(ofSize: 12, weight: .medium)
        refresh()
        buildMenu()
        timer = Timer.scheduledTimer(withTimeInterval: 60, repeats: true) { [weak self] _ in
            self?.refresh()
            self?.buildMenu()
        }
    }

    func refresh() {
        guard let data = FileManager.default.contents(atPath: cachePath),
              let obj = try? JSONSerialization.jsonObject(with: data),
              let payload = (obj as? [String: Any])?["payload"] as? [String: Any],
              let limits = payload["limits"] as? [[String: Any]] else {
            item.button?.title = "⚡ --"
            return
        }
        var leftPct = 100.0, leftMicro = 0.0, resetHours = 0.0, ageMinutes = 0.0
        var generated = ""
        for lim in limits {
            guard let weekly = lim["weekly"] as? [String: Any],
                  let bp = weekly["remainingBasisPoints"] as? Int else { continue }
            leftPct = Double(bp) / 100.0
            leftMicro = Double(weekly["remainingMicrocredits"] as? String ?? "0") ?? 0
            generated = payload["generatedAtIso"] as? String ?? ""
            if let resets = weekly["resetsAtIso"] as? String,
               let date = ISO8601DateFormatter().date(from: resets) {
                resetHours = max(0, date.timeIntervalSinceNow / 3600)
            }
        }
        let leftTokens = leftMicro * tokensPerMicrocredit()
        lastInfo = (leftPct, leftTokens, resetHours, generated, ageMinutes)

        if let genDate = ISO8601DateFormatter().date(from: generated) {
            ageMinutes = max(0, -genDate.timeIntervalSinceNow / 60)
        }
        let color: NSColor = leftPct <= 10 ? .systemRed
            : leftPct <= 25 ? .systemYellow
            : ageMinutes > 30 ? .disabledControlTextColor
            : .labelColor
        let prefix = ageMinutes > 30 ? "≈" : "⚡"
        let text = NSMutableAttributedString(
            string: String(format: "%@ %.1f%%", prefix, leftPct),
            attributes: [.foregroundColor: color, .font: NSFont.monospacedSystemFont(ofSize: 12, weight: .medium)]
        )
        item.button?.attributedTitle = text
    }

    func fmtM(_ n: Double) -> String {
        n >= 1e6 ? String(format: "%.1fM", n / 1e6) : String(format: "%.0fk", n / 1e3)
    }

    func buildMenu() {
        let menu = NSMenu()
        func row(_ title: String) {
            let mi = NSMenuItem(title: title, action: nil, keyEquivalent: "")
            mi.isEnabled = false
            menu.addItem(mi)
        }
        row(String(format: "Weekly limit left: %.1f%%", lastInfo.leftPct))
        row(String(format: "≈ %@ tokens left", fmtM(lastInfo.leftTokens)))
        row(lastInfo.resetHours >= 24
            ? String(format: "Resets in: %.1f days", lastInfo.resetHours / 24)
            : String(format: "Resets in: %.1f h", lastInfo.resetHours))
        row("Data as of: " + (lastInfo.generated.count >= 16 ? String(lastInfo.generated.suffix(9).prefix(5)) : "?") + (lastInfo.ageMinutes > 30 ? " (stale — open Bionic Settings → Billing and Usage)" : ""))
        menu.addItem(.separator())
        let open = NSMenuItem(title: "Open dashboard", action: #selector(openDashboard), keyEquivalent: "")
        open.target = self
        menu.addItem(open)
        menu.autoenablesItems = false
        item.menu = menu
    }

    @objc func openDashboard() {
        NSWorkspace.shared.open(URL(fileURLWithPath: dashPath + "/dashboard.html"))
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.accessory)
app.run()
