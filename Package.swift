// swift-tools-version: 5.10
// The swift-tools-version declares the minimum version of Swift required to build this package.

import PackageDescription

let pythonPath = "Frameworks/Python.xcframework"

let pythonBinaryTarget = Target.binaryTarget(
    name: "Python",
    path: pythonPath
)

let cPythonTarget = Target.target(
    name: "CPython",
    dependencies: [
        "Python"
    ],
    path: "Sources/CPython",
    publicHeadersPath: "."

)


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
    targets: [
        cPythonTarget,
        pythonBinaryTarget,
    ]
)
