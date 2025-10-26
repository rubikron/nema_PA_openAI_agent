"""Audio utility functions for voice pipeline."""
import curses
import numpy as np
import sounddevice as sd

SAMPLE_RATE = 24000
CHANNELS = 1
DTYPE = np.int16


def record_audio() -> np.ndarray:
    """
    Record audio from the microphone until the user presses any key.
    Uses curses to avoid requiring special permissions on macOS.

    Returns:
        np.ndarray: Recorded audio samples
    """
    def _record_with_curses(stdscr):
        stdscr.nodelay(True)  # Make getch() non-blocking
        stdscr.clear()
        stdscr.addstr(0, 0, "Recording... Press any key to stop")
        stdscr.refresh()

        chunks = []

        def callback(indata, frames, time, status):
            if status:
                print(f"Status: {status}")
            chunks.append(indata.copy())

        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            callback=callback
        ):
            while True:
                key = stdscr.getch()
                if key != -1:  # Any key pressed
                    break

        stdscr.addstr(1, 0, "Recording stopped.")
        stdscr.refresh()
        stdscr.getch()  # Wait for another key press before exiting

        if chunks:
            return np.concatenate(chunks, axis=0)
        return np.array([], dtype=DTYPE)

    return curses.wrapper(_record_with_curses)


class AudioPlayer:
    """
    Context manager for playing audio output.
    Streams audio to the speakers as it's received.
    """

    def __init__(self):
        self.stream = None

    def __enter__(self):
        self.stream = sd.OutputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE
        )
        self.stream.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.stream:
            self.stream.stop()
            self.stream.close()

    def add_audio(self, audio_data: bytes):
        """
        Add audio data to the playback stream.

        Args:
            audio_data: Raw audio bytes to play
        """
        if self.stream:
            audio_array = np.frombuffer(audio_data, dtype=DTYPE)
            self.stream.write(audio_array)
