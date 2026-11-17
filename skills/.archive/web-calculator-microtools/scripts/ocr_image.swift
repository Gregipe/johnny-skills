// macOS Vision OCR — reads text from a screenshot when vision_analyze / browser_vision
// cannot attach images to the session. Prints each recognized line with its normalized
// bounding box, sorted top-to-bottom (then left-to-right).
//
// Build & run:
//   swiftc -O ocr_image.swift -o ocr_image
//   ./ocr_image /path/to/image.png
//
// Output format: "[x,y width%] text" where x,y,width are 0-100 (percent of image).
import Vision
import AppKit

let args = CommandLine.arguments
guard args.count > 1 else { print("usage: ocr_image <image>"); exit(1) }
let path = args[1]
guard let img = NSImage(contentsOfFile: path),
      let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    print("ERR: cannot load \(path)"); exit(1)
}

let req = VNRecognizeTextRequest()
req.recognitionLevel = .accurate
req.usesLanguageCorrection = true

do {
    try VNImageRequestHandler(cgImage: cg).perform([req])
    let results = (req.results ?? []).sorted { a, b in
        // sort top-to-bottom, then left-to-right within a line
        let ay = 1 - a.boundingBox.midY, by = 1 - b.boundingBox.midY
        if abs(ay - by) > 0.02 { return ay < by }
        return a.boundingBox.midX < b.boundingBox.midX
    }
    for obs in results {
        guard let c = obs.topCandidates(1).first else { continue }
        let bb = obs.boundingBox
        let x = Int(round(bb.minX * 100))
        let y = Int(round((1 - bb.maxY) * 100))
        let w = Int(round(bb.width * 100))
        print("[\(x),\(y) \(w)w] \(c.string)")
    }
} catch {
    print("ERR: \(error)"); exit(1)
}
