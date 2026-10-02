# -*- coding: utf-8 -*-
"""跳转精度端到端测量：
seek(X) 后等到播放自然结束，墙钟耗时 ≈ (总长 - 实际解码起点)。
实测耗时与理论剩余时间的偏差 = 解码器寻址误差 + 缓冲量化。
同时测：重复 seek 同一目标的确定性、暂停/恢复连续性。"""
import os
import shutil
import sys
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lrc_editor import AudioPlayer

def measure_seek_to_end(a, target_ms, length_ms, reps=1):
    errs = []
    for _ in range(reps):
        a.seek(target_ms)
        t0 = time.perf_counter()
        while not a.ended():
            time.sleep(0.002)
        elapsed = time.perf_counter() - t0
        remaining = (length_ms - target_ms) / 1000
        errs.append(elapsed - remaining)
    return errs

def make_test_audio():
    """在临时目录生成 8 秒同源测试音频（wav + mp3 CBR/VBR + ogg），返回路径列表"""
    import math
    import struct
    import subprocess
    import tempfile
    import wave

    d = tempfile.mkdtemp(prefix="lrc_bench_")
    wav = os.path.join(d, "t.wav")
    w = wave.open(wav, "w")
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
    n = 44100 * 8
    w.writeframes(b"".join(struct.pack(
        "<h", int(12000 * math.sin(2 * math.pi * 440 * t / 44100))) for t in range(n)))
    w.close()
    files = [(wav, "WAV")]
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        for name, args in (("t_cbr.mp3", ["-b:a", "192k"]),
                           ("t_vbr.mp3", ["-q:a", "4"]),
                           ("t.ogg", ["-q:a", "4"])):
            out = os.path.join(d, name)
            r = subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", wav] + args + [out],
                               capture_output=True)
            if r.returncode == 0:
                files.append((out, "MP3 CBR192" if "cbr" in name else ("MP3 VBR" if "vbr" in name else "OGG")))
    return files, d


def main():
    files, tmpdir = make_test_audio()
    files = [(p, n) for p, n in files]
    print(f"{'格式':<10} {'目标':<8} {'误差ms(min/mean/max)':<28}")
    for path, name in files:
        a = AudioPlayer()
        try:
            a.load(path)
        except Exception as ex:
            print(f"{name:<10} 加载失败: {ex}")
            continue
        length = a.length_ms
        rows = []
        for target in (1000, 3000, 5000):
            if target >= length - 500:
                continue
            errs = measure_seek_to_end(a, target, length)
            rows.append((target, min(errs)*1000, sum(errs)/len(errs)*1000, max(errs)*1000))
        # 同一目标重复 5 次：确定性
        errs = measure_seek_to_end(a, 5000, length, reps=5)
        det = (max(errs)-min(errs))*1000
        a.stop(); a.pygame.mixer.quit()
        for target, mn, mean, mx in rows:
            print(f"{name:<10} {target}ms   {mn:+7.1f} / {mean:+7.1f} / {mx:+7.1f}")
        print(f"{name:<10} 重复5次极差: {det:.1f} ms   (总长实测 {length:.0f}ms)")

    # 暂停/恢复连续性（wav）
    a = AudioPlayer(); a.load(files[0][0])
    a.play(); time.sleep(0.5); a.pause()
    p1 = a.get_pos(); time.sleep(0.4); a.resume(); time.sleep(0.4); a.pause()
    p2 = a.get_pos()
    gap = (p2 - p1) - 400
    print(f"暂停恢复连续性: 暂停期间位置不变, 恢复后 400ms 实际走了 {p2-p1-400:.1f}ms 偏差")
    a.stop(); a.pygame.mixer.quit()
    shutil.rmtree(tmpdir, ignore_errors=True)

if __name__ == "__main__":
    main()
