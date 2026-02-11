import Cocoa

class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSAppleEventManager.shared().setEventHandler(
            self,
            andSelector: #selector(handleGetURL(event:reply:)),
            forEventClass: AEEventClass(kInternetEventClass),
            andEventID: AEEventID(kAEGetURL)
        )
    }

    @objc func handleGetURL(event: NSAppleEventDescriptor, reply: NSAppleEventDescriptor) {
        guard let urlString = event.paramDescriptor(forKeyword: keyDirectObject)?.stringValue else {
            NSLog("claunch: no URL in Apple Event")
            NSApplication.shared.terminate(nil)
            return
        }

        let bundle = Bundle.main
        guard let handlerPath = bundle.path(forResource: "handler", ofType: "py") else {
            NSLog("claunch: handler.py not found in app bundle")
            NSApplication.shared.terminate(nil)
            return
        }

        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
        process.arguments = [handlerPath, urlString]
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
app.run()
