// swift-tools-version: 6.0
// The swift-tools-version declares the minimum version of Swift required to build this package.

import PackageDescription
import Foundation

let processInfo = ProcessInfo.processInfo


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
        // For Android, the Swift SDK should be configured with the correct NDK sysroot
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
                ],
                
            )
        ]
    case .linux, .windows, .webassembly:
        fatalError("CPython package is not supported on \(platform) yet.")
    case .apple:
        let pythonPath = "Frameworks/Python.xcframework"

        let pythonBinaryTarget = Target.binaryTarget(
            name: "Python",
            path: pythonPath
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
                ],

            ),
            pythonBinaryTarget
        ]
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
