//
//  PackageHelpers.swift
//  CPython
//
//  Created by CodeBuilder on 19/10/2025.
//

import PackageDescription

let frameworksPath = "Frameworks"
let pythonPath = "\(frameworksPath)/libPython.xcframework"
let pythonHeaders = "\(pythonPath)/ios-arm64/Python.framework/Headers"





func pythonFrameworkFlags(_ seperated: Bool) -> [String] {
    if seperated {
        [
            "-F", "\(pythonPath)/ios-arm64",
            "-F", "\(pythonPath)/ios-arm64_x86_64-simulator",
            "-F", "\(pythonPath)/macos-arm64_x86_64",
            //"-framework", "Python"
        ]
    } else {
        [
            "-F\(pythonPath)/ios-arm64",
            "-F\(pythonPath)/ios-arm64_x86_64-simulator",
            "-F\(pythonPath)/macos-arm64_x86_64",
            //"-framework", "Python"
        ]
    }
}

func pythonHeaderFlags(_ seperated: Bool) -> [String] {
    if seperated {
        [
            "-I", pythonHeaders
        ]
    } else {
        [
            "-I\(pythonHeaders)"
        ]
    }
}

let python_framework_flags: [String] = [
    "-F", "\(pythonPath)/ios-arm64",
    "-F", "\(pythonPath)/ios-arm64_x86_64-simulator",
    "-F", "\(pythonPath)/macos-arm64_x86_64"
]

let python_header_flags: [String] = [
    
]
