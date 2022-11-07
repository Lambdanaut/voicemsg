from array import array
import abc
from collections.abc import Callable
import os
from queue import Queue, Full
import statistics
import sys
import time
import threading
from typing import Optional

import pyaudio
import playsound
import wave

sys.path.append('.')


p = pyaudio.PyAudio()


class Audio(abc.ABC):
    @abc.abstractmethod
    def play(self, filepath: str):
        pass

    @abc.abstractmethod
    def record(self, filepath: str):
        """
        Records audio for `duration` seconds and saves it to `filepath`

        :param filepath: Filepath to save recording
        :param duration: Duration in seconds
        :return:
        """
        pass


class VoiceMsg(Audio):
    sample_rate = 44100
    channels = 1  # 1 for mono, 2 for stereo
    chunk_size = 1024
    buf_max_size = chunk_size * 10  # if the recording thread can't consume fast enough, the listener will start discarding
    format = pyaudio.paInt16

    def __init__(
            self,
            filepath: str,
            max_duration: int = 12,
            silence_threshold: int = 90,  # Anything below this volume is considered silent
            silence_duration: float = 1.0,  # Number of seconds to look back on to count silence duration
            debug: bool = False):

        """
        Usage:
            vm = VoiceMsg(".")
            vm.calibrate(show_demo_text=True)  # Calibrates the silence threshold
            vm.record("test.wav")  # Records a segment of audio until silence is heard
            vm.play("test.wav")


        :param filepath: filepath to save the final recording to
        :param max_duration: Maximum length of a complete recording. Will cut early if silence is detected
        :param silence_threshold: The upper bound for how quiet is silent in dFBS
        -32 is a pretty good default for recording speech.
        :param silence_duration: How long to record over and over, detecting silences
        """

        self.max_duration = max_duration
        self.silence_threshold = silence_threshold
        self.silence_duration = silence_duration
        self.filepath = filepath
        self.debug = debug

    def _filepath_from_filename(self, filename: str) -> str:
        return os.path.join(self.filepath, filename)

    def _is_silent(self, frames: list) -> bool:
        for frame in frames:
            volume = max(frame)
            if volume > self.silence_threshold:
                return False
        return True

    def print_chunk_volume(self, chunk: list):
        vol = max(chunk)
        print('█' * int(vol / 100))

    def calibrate(self, show_demo_text: bool = True):
        """
        Sets the silence_threshold after a calibration period of detected silence.
        """
        # Play calibration beginning audio
        if show_demo_text:
            print("Calibration process started")
            print("===========================")

        time.sleep(0.2)  # Shortest sleep while the microphone warms up.. or something. Trust me it's important

        if show_demo_text:
            print(" - Remain silent for 4 seconds")

        frame_volumes = []  # Initialize list to store frames

        # Store data in chunks for 4.0 seconds
        duration: float = 4.0
        stream = p.open(format=self.format,
                        channels=self.channels,
                        rate=self.sample_rate,
                        frames_per_buffer=self.chunk_size,
                        input=True)
        for i in range(0, int(self.sample_rate / self.chunk_size * duration)):
            volume = max(stream.read(self.chunk_size))
            frame_volumes.append(volume)

        # A bit noisier than the median average of samples
        calibrated_value = int(statistics.median(frame_volumes) * 2.0)

        self.silence_threshold = calibrated_value

        # Play calibration complete audio
        if show_demo_text:
            print("Calibration process complete!")
            print("Calibrated silence threshold set to `{}`".format(self.silence_threshold))

        return calibrated_value

    def play(self, filename: str):
        filepath = self._filepath_from_filename(filename)
        playsound.playsound(filepath)

    def record(self, filename: str, stream_callback: Optional[Callable] = None):
        """
        Records in chunks of self.silence_duration until another silence is reached

        :param filename: Filename to store the recording in at self.filepath
        :param stream_callback: Optional function to call every time a frame is read. Frame is passed in as input.
        :raises NoAudioHeardException: Raised if no audio is heard at all for 20 times the silence_duration
        :return:
        """

        stopped_event = threading.Event()
        _event = threading.Event()

        def _record_to_file(stopped, q):
            duration_so_far: float = 0.0
            frames: list = []

            while True:
                if stopped.wait(timeout=0):
                    # End this thread if we get a stop event
                    break

                # Keep track of how many chunks of time we've processed
                duration_so_far += self.silence_duration

                # Read the chunks from the queue until we have an audio that is self.silence_duration in length
                frames_to_inspect = []
                for i in range(0, int(self.sample_rate / self.chunk_size * self.silence_duration)):
                    frame = q.get()

                    if self.debug:
                        self.print_chunk_volume(frame)  # Debug print chunk volume

                    frames_to_inspect.append(frame)

                is_silent = self._is_silent(frames_to_inspect)

                if not is_silent:
                    # Add the new frames to the ongoing buffer if it's not silent
                    frames += frames_to_inspect

                if is_silent:
                    if frames or (not frames and duration_so_far > self.silence_duration * 20):
                        # If we've recorded at least one non-silent chunk
                        # or if no audio was ever recorded for 20 times the length of a silence duration

                        # Save as WAV file
                        filepath = self._filepath_from_filename(filename)

                        # open the file in 'write bytes' mode
                        wf = wave.open(filepath, "wb")
                        # set the channels
                        wf.setnchannels(self.channels)
                        # set the sample format
                        wf.setsampwidth(p.get_sample_size(self.format))
                        # set the sample rate
                        wf.setframerate(self.sample_rate)
                        # write the frames as bytes
                        wf.writeframes(b"".join(frames))
                        # close the file
                        wf.close()

                        stopped_event.set()

        def _listen(stopped, q):
            stream = pyaudio.PyAudio().open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size,
            )

            while True:
                if stopped.wait(timeout=0):
                    break
                try:
                    chunk = array('h', stream.read(self.chunk_size))
                    if stream_callback is not None:
                        stream_callback(chunk)
                    q.put(chunk)
                except Full:
                    pass  # discard

        q = Queue(maxsize=int(round(self.buf_max_size / self.chunk_size)))

        listen_t = threading.Thread(target=_listen, args=(stopped_event, q))
        listen_t.start()
        record_t = threading.Thread(target=_record_to_file, args=(stopped_event, q))
        record_t.start()

        try:
            while True:
                listen_t.join(0.1)
                record_t.join(0.1)

                if stopped_event.wait(timeout=0):
                    break

        except KeyboardInterrupt:
            stopped_event.set()

        except OSError:
            print("Warning: OSError encountered while listening to audio from voicemsg")
            stopped_event.set()

        listen_t.join()
        record_t.join()


if __name__ == '__main__':
    # Run demo
    vm = VoiceMsg(".", debug=True)
    vm.calibrate(show_demo_text=True)  # Calibrates the silence threshold
    vm.record("test.wav")  # Records a segment of audio until silence is heard
    vm.play("test.wav")
