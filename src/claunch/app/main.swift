import Cocoa

class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        // Handler already registered before app.run() to avoid race condition
    }

    func application(_ application: NSApplication, open urls: [URL]) {
        guard let url = urls.first else { return }
        launchHandler(urlString: url.absoluteString)
    }

    func findUV() -> String? {
        let home = FileManager.default.homeDirectoryForCurrentUser.path
        let candidates = [
            "\(home)/.local/bin/uv",
            "/opt/homebrew/bin/uv",
            "/usr/local/bin/uv",
            "\(home)/.cargo/bin/uv",
            "\(home)/.pyenv/shims/uv",
        ]
        for path in candidates {
            if FileManager.default.isExecutableFile(atPath: path) {
                return path
            }
        }
        return nil
    }

    @objc func handleGetURL(event: NSAppleEventDescriptor, reply: NSAppleEventDescriptor) {
        guard let urlString = event.paramDescriptor(forKeyword: keyDirectObject)?.stringValue else {
            NSLog("claunch: no URL in Apple Event")
            NSApplication.shared.terminate(nil)
            return
        }
        launchHandler(urlString: urlString)
    }

    func launchHandler(urlString: String) {
        NSLog("claunch: handling URL: %@", urlString)

        let bundle = Bundle.main
        guard let handlerPath = bundle.path(forResource: "handler", ofType: "py") else {
            NSLog("claunch: handler.py not found in app bundle")
            NSApplication.shared.terminate(nil)
            return
        }

        let process = Process()
        if let uvPath = findUV() {
            process.executableURL = URL(fileURLWithPath: uvPath)
            process.arguments = ["run", "--no-project", handlerPath, urlString]
        } else {
            process.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
            process.arguments = [handlerPath, urlString]
        }
        process.terminationHandler = { _ in
            DispatchQueue.main.async {
                NSApplication.shared.terminate(nil)
            }
        }

        do {
            try process.run()
        } catch {
            NSLog("claunch: failed to run handler: \(error)")
            NSApplication.shared.terminate(nil)
        }
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate

// Register URL handler BEFORE app.run() to avoid missing events during launch
NSAppleEventManager.shared().setEventHandler(
    delegate,
    andSelector: #selector(AppDelegate.handleGetURL(event:reply:)),
    forEventClass: AEEventClass(kInternetEventClass),
    andEventID: AEEventID(kAEGetURL)
)

app.run()
