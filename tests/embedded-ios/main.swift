import UIKit
import WebKit

// A plain WKWebView in a disposable Simulator app. No WeChat bridge is installed.
final class App: UIResponder, UIApplicationDelegate, WKScriptMessageHandler {
    var window: UIWindow?
    var web: WKWebView!
    var stage = "boot"
    var game = ""
    var output: URL { FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0] }

    func application(_ app: UIApplication, didFinishLaunchingWithOptions options: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        game = ProcessInfo.processInfo.arguments.last ?? ""
        let destinations = ["garden": "https://cyber-cemetery-proto.pages.dev/", "mountain": "https://yunqi-shanzhong-v2-play.pages.dev/"]
        guard let address = destinations[game], let url = URL(string: address),
              let script = Bundle.main.url(forResource: "route", withExtension: "js"),
              let code = try? String(contentsOf: script, encoding: .utf8) else { return false }
        let config = WKWebViewConfiguration()
        config.userContentController.add(self, name: "report")
        config.userContentController.addUserScript(WKUserScript(source: code, injectionTime: .atDocumentEnd, forMainFrameOnly: true))
        web = WKWebView(frame: .zero, configuration: config)
        let root = UIViewController()
        root.view.backgroundColor = .systemBackground
        root.view.addSubview(web)
        web.translatesAutoresizingMaskIntoConstraints = false
        let safe = root.view.safeAreaLayoutGuide
        NSLayoutConstraint.activate([web.leadingAnchor.constraint(equalTo: safe.leadingAnchor), web.trailingAnchor.constraint(equalTo: safe.trailingAnchor), web.topAnchor.constraint(equalTo: safe.topAnchor, constant: 44), web.bottomAnchor.constraint(equalTo: safe.bottomAnchor)])
        window = UIWindow(frame: UIScreen.main.bounds)
        window?.rootViewController = root
        window?.makeKeyAndVisible()
        web.load(URLRequest(url: url))
        return true
    }

    func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
        guard let text = message.body as? String else { return }
        stage = text
        try? text.write(to: output.appendingPathComponent(game + ".txt"), atomically: true, encoding: .utf8)
    }

    func applicationDidBecomeActive(_ app: UIApplication) {
        if stage == "ready" {
            web.evaluateJavaScript("window.checkAfterResume()", completionHandler: nil)
        }
    }
}

UIApplicationMain(CommandLine.argc, CommandLine.unsafeArgv, nil, NSStringFromClass(App.self))
