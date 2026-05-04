// swift-tools-version: 6.0
// The swift-tools-version declares the minimum version of Swift required to build this package.

import PackageDescription
import Foundation

let processInfo = ProcessInfo.processInfo
let pipMode = processInfo.environment["PIP_MODE"] != nil


enum BuildPlatform: String {
    case apple
    case linux
    case windows
    case android
    case webassembly
}

func getPlatform() -> BuildPlatform {
    if processInfo.environment["SWIFT_ANDROID_HOME"] != nil {
        return .android
    }

    return .apple
}

// Find Android NDK sysroot for standard C headers
func findAndroidNDKSysroot() -> String? {
    // Check ANDROID_NDK_HOME first
    if let ndkHome = processInfo.environment["ANDROID_NDK_HOME"] {
        let sysroot = "\(ndkHome)/toolchains/llvm/prebuilt/darwin-x86_64/sysroot"
        if FileManager.default.fileExists(atPath: sysroot) {
            return sysroot
        }
    }
    
    // Check ANDROID_HOME/ndk
    if let androidHome = processInfo.environment["ANDROID_HOME"] {
        let ndkDir = "\(androidHome)/ndk"
        if let versions = try? FileManager.default.contentsOfDirectory(atPath: ndkDir) {
            // Sort to get the latest version
            if let latestVersion = versions.sorted().last {
                let sysroot = "\(ndkDir)/\(latestVersion)/toolchains/llvm/prebuilt/darwin-x86_64/sysroot"
                if FileManager.default.fileExists(atPath: sysroot) {
                    return sysroot
                }
            }
        }
    }
    
    // Default location on macOS
    let defaultNDK = ProcessInfo.processInfo.environment["HOME"].map { home in
        "\(home)/Library/Android/sdk/ndk"
    }
    if let ndkDir = defaultNDK, FileManager.default.fileExists(atPath: ndkDir) {
        if let versions = try? FileManager.default.contentsOfDirectory(atPath: ndkDir) {
            if let latestVersion = versions.sorted().last {
                let sysroot = "\(ndkDir)/\(latestVersion)/toolchains/llvm/prebuilt/darwin-x86_64/sysroot"
                if FileManager.default.fileExists(atPath: sysroot) {
                    return sysroot
                }
            }
        }
    }
    
    return nil
}

func getTargets() -> [Target] {
    let platform = getPlatform()
    switch platform {
    case .android:
        if pipMode {
            // Android PIP_MODE: link against the running Python interpreter (for cibuildwheel).
            // No bundled headers — Python headers are located via the -Xcc -isystem flag.
            // PIP_MODE is defined so CPython.h skips the bundled-headers branch.
            // --allow-shlib-undefined lets the .so be built without linking libpython
            // (Python is already loaded in the interpreter process at import time).
            //
            // STDINT FIX: SPM adds the Swift toolchain's clang resource dir as a user -I
            // path (e.g. /lib/clang/21/include). When Xcode's clang processes
            // #include <stdint.h>, it finds clang/21/stdint.h first which sets the
            // __CLANG_STDINT_H guard and does #include_next — which finds Xcode's own
            // clang/17/stdint.h. That file's guard is ALREADY SET (same macro), so it
            // skips its #include_next to the NDK sysroot, and uint32_t is never defined.
            // Fix: add the NDK sysroot usr/include as an explicit user -I path (placed
            // first, before clang/21) so NDK's stdint.h is found and processed directly.
            let ndkSysrootInclude: String = {
                let home = processInfo.environment["HOME"] ?? ""
                let sdk  = processInfo.environment["SWIFT_SDK"] ?? ""
                let canonical = "\(home)/Library/org.swift.swiftpm/swift-sdks/\(sdk).artifactbundle/swift-android/ndk-sysroot/usr/include"
                if FileManager.default.fileExists(atPath: canonical) { return canonical }
                // Fallback: scan for any installed android SDK bundle.
                let sdkDir = "\(home)/Library/org.swift.swiftpm/swift-sdks"
                if let bundles = try? FileManager.default.contentsOfDirectory(atPath: sdkDir) {
                    for b in bundles.filter({ $0.contains("android") }) {
                        let p = "\(sdkDir)/\(b)/swift-android/ndk-sysroot/usr/include"
                        if FileManager.default.fileExists(atPath: p) { return p }
                    }
                }
                return ""
            }()
            var cflags: [CSetting] = [
                .define("PIP_MODE"),
            ]
            if !ndkSysrootInclude.isEmpty {
                cflags.append(.unsafeFlags(["-isystem", ndkSysrootInclude]))
            }
            return [
                .target(
                    name: "CPython",
                    path: "Sources/CPython",
                    publicHeadersPath: ".",
                    cSettings: cflags,
                    swiftSettings: [
                        .swiftLanguageMode(.v5),
                    ],
                    linkerSettings: [
                        .unsafeFlags(["-Xlinker", "--allow-shlib-undefined"]),
                    ]
                )
            ]
        } else {
            // Old Android setup: Swift SDK configured with NDK sysroot,
            // bundled PythonHeaders-android, explicit libpython linkage.
            // via: swift sdk configure <sdk-name> <triple> --sdk-root-path <ndk-sysroot-path>
            // But C compilation also needs the sysroot include path

            let cSettings: [CSetting] = [
                .define("PY_SSIZE_T_CLEAN"),
                // Use Android-specific Python headers
                .headerSearchPath("../../PythonHeaders-android"),
            ]

            // Note: Don't set -isysroot here - the Swift SDK for Android already configures
            // the sysroot correctly. Setting it again causes conflicts.

            return [
                .target(
                    name: "CPython",
                    path: "Sources/CPython",
                    publicHeadersPath: ".",
                    cSettings: cSettings,
                    swiftSettings: [
                        .swiftLanguageMode(.v5)
                    ],
                    linkerSettings: [
                        .linkedLibrary("python3.13"),
                    ]
                )
            ]
        }
    case .linux, .windows, .webassembly:
        fatalError("CPython package is not supported on \(platform) yet.")
    case .apple:
        if pipMode {
            // PIP_MODE: link against the running Python interpreter (for cibuildwheel / pip installs).
            // No xcframework embedded — Python symbols resolve via -undefined dynamic_lookup at load time.
            //
            // Python headers are located via the CPATH env var, which clang inherits for ALL
            // compilation units in the build — no per-target -I flag needed.
            // Set CPATH before invoking swift build, e.g. in setup.py:
            //   os.environ["CPATH"] = sysconfig.get_path("include")
            return [
                .target(
                    name: "CPython",
                    path: "Sources/CPython",
                    publicHeadersPath: ".",
                    swiftSettings: [
                        .swiftLanguageMode(.v5),
                    ],
                    linkerSettings: [
                        // -Xlinker wrapper is required for swiftc to forward these to ld correctly.
                        .unsafeFlags(["-Xlinker", "-undefined", "-Xlinker", "dynamic_lookup"]),
                    ]
                )
            ]
        } else {
            // Normal mode: embed Python.xcframework (standard Swift package usage).
            let pythonBinaryTarget = Target.binaryTarget(
                name: "Python",
                path: "Frameworks/Python.xcframework"
            )
            return [
                .target(
                    name: "CPython",
                    dependencies: [
                        "Python"
                    ],
                    path: "Sources/CPython",
                    publicHeadersPath: ".",
                    swiftSettings: [
                        .swiftLanguageMode(.v5)
                    ]
                ),
                pythonBinaryTarget
            ]
        }
    }
}


// old target definition:
// let cPythonTarget = Target.target(
//     name: "CPython",
//     dependencies: [
//         "Python"
//     ],
//     path: "Sources/CPython",
//     publicHeadersPath: "."

// )



let package = Package(
    name: "CPython",
    products: [
        .library(
            name: "CPython",
            targets: [
                "CPython"
            ]
        )
    ],
    targets: getTargets()
)
