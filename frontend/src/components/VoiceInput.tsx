import { useEffect, useRef, useState } from "react";
import { errorCode, transcribeVoice, voiceAvailable } from "../api/topicE";

const MIME = "audio/webm;codecs=opus";
const MAX_BYTES = 2_000_000;
const MAX_SECONDS = 30;
type State = "idle" | "requesting" | "recording" | "transcribing";

const ERRORS: Record<string, string> = {
  voice_too_large: "The recording is too large. Please record a shorter message.",
  voice_content_type: "This browser could not produce a supported audio recording.",
  voice_no_speech: "No speech was recognised. Please try again.",
  voice_duration_limit: "Please keep your recording under 30 seconds.",
  voice_transcript_too_long: "Please record a shorter message, up to 500 characters.",
  voice_protection_failed: "The transcript could not be protected. Please try typing your request.",
  voice_unavailable: "Voice input is unavailable. You can still type your request.",
  rate_limited: "You have reached the voice limit. Please wait a minute before trying again.",
};

/** Recording stays in memory. The protected transcript is never submitted automatically. */
export function VoiceInput({ onTranscript }: { onTranscript: (text: string) => void }) {
  const [available, setAvailable] = useState(false);
  const [state, setState] = useState<State>("idle");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const chunks = useRef<Blob[]>([]);
  const size = useRef(0);
  const startedAt = useRef(0);
  const stoppedAt = useRef(0);
  const timer = useRef<number | null>(null);
  const generation = useRef(0);
  const upload = useRef<AbortController | null>(null);

  const release = () => {
    if (timer.current !== null) window.clearTimeout(timer.current);
    timer.current = null;
    const current = recorder.current;
    recorder.current = null;
    if (current) {
      current.ondataavailable = null;
      current.onstop = null;
      current.onerror = null;
      if (current.state !== "inactive") current.stop();
    }
    stream.current?.getTracks().forEach((track) => track.stop());
    stream.current = null;
    chunks.current = [];
    size.current = 0;
    upload.current?.abort();
    upload.current = null;
  };

  useEffect(() => {
    let active = true;
    const supported = window.isSecureContext && typeof MediaRecorder !== "undefined"
      && Boolean(navigator.mediaDevices?.getUserMedia) && MediaRecorder.isTypeSupported(MIME);
    if (supported) voiceAvailable().then((yes) => active && setAvailable(yes)).catch(() => {});
    return () => {
      active = false;
      generation.current += 1;
      release();
    };
  }, []);

  const stop = () => {
    if (!recorder.current || recorder.current.state !== "recording") return;
    stoppedAt.current = performance.now();
    if (timer.current !== null) window.clearTimeout(timer.current);
    timer.current = null;
    recorder.current.stop();
    stream.current?.getTracks().forEach((track) => track.stop());
    stream.current = null;
    setState("transcribing");
  };

  const fail = (message: string) => {
    generation.current += 1;
    release();
    setState("idle");
    setError(message);
  };

  const start = async () => {
    const run = ++generation.current;
    setState("requesting");
    setError("");
    setNotice("");
    try {
      const recordingStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (generation.current !== run) {
        recordingStream.getTracks().forEach((track) => track.stop());
        return;
      }
      stream.current = recordingStream;
      const current = new MediaRecorder(recordingStream, { mimeType: MIME, audioBitsPerSecond: 64_000 });
      recorder.current = current;
      chunks.current = [];
      size.current = 0;
      stoppedAt.current = 0;
      current.ondataavailable = (event) => {
        if (generation.current !== run || !event.data.size) return;
        if (size.current + event.data.size > MAX_BYTES) {
          fail(ERRORS.voice_too_large);
          return;
        }
        chunks.current.push(event.data);
        size.current += event.data.size;
      };
      current.onerror = () => {
        if (generation.current === run) fail("Recording failed. Please try again.");
      };
      current.onstop = async () => {
        if (generation.current !== run) return;
        const seconds = ((stoppedAt.current || performance.now()) - startedAt.current) / 1000;
        // A suspended/background tab can delay its timer; discard an overlong clip.
        if (seconds > MAX_SECONDS) {
          fail(ERRORS.voice_duration_limit);
          return;
        }
        const audio = new Blob(chunks.current, { type: MIME });
        chunks.current = [];
        current.ondataavailable = null;
        current.onstop = null;
        current.onerror = null;
        recorder.current = null;
        stream.current?.getTracks().forEach((track) => track.stop());
        stream.current = null;
        if (timer.current !== null) window.clearTimeout(timer.current);
        timer.current = null;
        if (!audio.size || seconds <= 0) {
          fail("The recording was empty. Please try again.");
          return;
        }
        setState("transcribing");
        const controller = new AbortController();
        upload.current = controller;
        try {
          const text = await transcribeVoice(audio, seconds, controller.signal);
          if (generation.current !== run) return;
          onTranscript(text);
          setNotice("Review the protected transcript in the input box, then press Send when ready.");
        } catch (e) {
          if (generation.current !== run) return;
          const code = errorCode(e);
          if (code === "voice_unavailable") setAvailable(false);
          setError(ERRORS[code] ?? "Voice input failed. Please try again or type your request.");
        } finally {
          if (generation.current === run) {
            upload.current = null;
            size.current = 0;
            setState("idle");
          }
        }
      };
      startedAt.current = performance.now();
      current.start(250);
      // Stop slightly early to allow for normal timer scheduling latency.
      timer.current = window.setTimeout(stop, MAX_SECONDS * 1000 - 250);
      setState("recording");
    } catch (e) {
      if (generation.current !== run) return;
      fail(e instanceof DOMException && e.name === "NotAllowedError"
        ? "Microphone access was blocked. You can still type your request."
        : "The microphone could not start. Please try again.");
    }
  };

  const toggle = () => {
    if (state === "recording") stop();
    else if (state === "requesting") {
      generation.current += 1;
      release();
      setState("idle");
    } else if (state === "idle") void start();
  };

  return (
    <div className="fb-voice-input">
      {available && <button type="button" className={`fb-icon-btn${state === "recording" ? " is-recording" : ""}`}
        onClick={toggle} disabled={state === "transcribing"} aria-pressed={state === "recording"}
        title="Record up to 30 seconds. Audio is sent for transcription; review the text before sending."
        aria-label={state === "recording" ? "Stop recording" : state === "requesting" ? "Cancel microphone request" : "Record voice input"}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="9" y="2" width="6" height="12" rx="3" /><path d="M5 10a7 7 0 0 0 14 0M12 19v3" /></svg>
      </button>}
      {state !== "idle" && <span className="fb-fine" role="status">{state === "recording" ? "Recording · click to stop (30 seconds maximum)" : state === "requesting" ? "Waiting for microphone access…" : "Preparing your transcript…"}</span>}
      {notice && <span className="fb-fine" role="status">{notice}</span>}
      {error && <span className="fb-fine" role="alert">{error}</span>}
    </div>
  );
}
