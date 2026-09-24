// Record only the Conversational DNA Chrome window, including when occluded.
// Requires macOS 15+ and Screen Recording permission for the invoking terminal.
import Foundation
import AppKit
import ScreenCaptureKit
import AVFoundation

final class RecorderDelegate: NSObject, SCRecordingOutputDelegate {
    var finished = false
    var failure: Error?
    let logURL: URL
    init(_ url: URL) { logURL=url }
    func recordingOutputDidStartRecording(_ recordingOutput: SCRecordingOutput) {
        let payload: [String: Any] = ["started_epoch_ms": Date().timeIntervalSince1970*1000, "kind":"continuous Chrome-window capture", "audio":"none"]
        try? JSONSerialization.data(withJSONObject:payload, options:.prettyPrinted).write(to:logURL)
        print("RECORDING_STARTED", Date().timeIntervalSince1970); fflush(stdout)
    }
    func recordingOutputDidFinishRecording(_ recordingOutput: SCRecordingOutput) { finished=true }
    func recordingOutput(_ recordingOutput: SCRecordingOutput, didFailWithError error: Error) { failure=error;finished=true }
}

@main struct WindowRecorder {
    @MainActor static func main() async throws {
        _ = NSApplication.shared
        let args=CommandLine.arguments
        let content=try await SCShareableContent.excludingDesktopWindows(true,onScreenWindowsOnly:false)
        let windows=content.windows.filter{$0.owningApplication?.bundleIdentifier=="com.google.Chrome" && ($0.title ?? "").contains("Conversational DNA") && $0.frame.width>600}
        for candidate in windows {print("CANDIDATE",candidate.windowID,candidate.frame,candidate.isOnScreen,candidate.title ?? "")}
        guard let window=windows.max(by:{$0.frame.width*$0.frame.height < $1.frame.width*$1.frame.height}) else {
            throw NSError(domain:"DNARecorder",code:1,userInfo:[NSLocalizedDescriptionKey:"No Chrome window titled Conversational DNA is available."])
        }
        print("WINDOW",window.windowID,"FRAME",window.frame);fflush(stdout)
        if args.count<3 { return }
        let url=URL(fileURLWithPath:args[1]);let seconds=Double(args[2])!
        let filter=SCContentFilter(desktopIndependentWindow:window)
        print("CONTENT",filter.contentRect,"SCALE",filter.pointPixelScale);fflush(stdout)
        let config=SCStreamConfiguration()
        config.width=Int(filter.contentRect.width*Double(filter.pointPixelScale))/2*2
        config.height=Int(filter.contentRect.height*Double(filter.pointPixelScale))/2*2
        // Reserve enough height to retain native width if a full-screen Space reports stale window bounds.
        // Unused black padding and browser chrome are cropped once during delivery.
        config.height=max(config.height,config.width*3/4)
        config.minimumFrameInterval=CMTime(value:1,timescale:30)
        config.queueDepth=6;config.showsCursor=false;config.capturesAudio=false
        config.captureResolution = .best
        config.ignoreShadowsSingleWindow=true
        let stream=SCStream(filter:filter,configuration:config,delegate:nil)
        let outConfig=SCRecordingOutputConfiguration()
        outConfig.outputURL=url;outConfig.videoCodecType = .h264;outConfig.outputFileType = .mp4
        let delegate=RecorderDelegate(url.appendingPathExtension("json"))
        let output=SCRecordingOutput(configuration:outConfig,delegate:delegate)
        try stream.addRecordingOutput(output)
        try await stream.startCapture()
        try await Task.sleep(nanoseconds:UInt64(seconds*1_000_000_000))
        try await stream.stopCapture()
        for _ in 0..<100 { if delegate.finished {break};try await Task.sleep(nanoseconds:100_000_000) }
        if let error=delegate.failure {throw error}
        guard delegate.finished else {throw NSError(domain:"DNARecorder",code:2,userInfo:[NSLocalizedDescriptionKey:"Recording did not finish."])}
        print("RECORDING_FINISHED",CMTimeGetSeconds(output.recordedDuration));fflush(stdout)
    }
}
