# -*- coding: utf-8 -*-
"""文件夹播放列表 + 上/下一首 + 切换保存确认 的自动化测试"""
import os
import sys
import time
import wave
import struct
import tempfile
import tkinter.messagebox as mb

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lrc_editor
from lrc_editor import LrcEditor, LrcLine


def make_wav(path, seconds=1.0):
    w = wave.open(path, "w")
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050)
    n = int(22050 * seconds)
    w.writeframes(b"".join(struct.pack("<h", int(9000 * ((t // 800) % 2))) for t in range(n)))
    w.close()


def main():
    tmp = tempfile.mkdtemp(prefix="lrc_pl_")
    p1, p2, p3 = (os.path.join(tmp, f"0{i}.wav") for i in (1, 2, 3))
    make_wav(p1); make_wav(p2); make_wav(p3)
    lrc2 = os.path.join(tmp, "02.lrc")
    open(lrc2, "w", encoding="utf-8").write("[ti:第二首]\n[00:01.00]甲\n[00:02.00]乙\n")

    app = LrcEditor()
    app.withdraw()
    orig_confirm = lrc_editor.messagebox.askyesnocancel
    answers = []
    lrc_editor.messagebox.askyesnocancel = lambda *a, **k: answers.pop(0)
    lrc_editor.filedialog.askdirectory = lambda *a, **k: tmp

    # --- 1. 打开文件夹：扫描 + 自动切到第 1 首 ---
    app.open_folder()
    assert len(app.playlist) == 3, app.playlist
    assert app._pl_index == 0 and app.audio.loaded_path == p1
    assert not app.lines and not app.meta
    assert app.empty_state.place_info(), "无 LRC 占位应显示"
    assert app.pl_list.get(0).startswith("▶"), app.pl_list.get(0)
    assert "1/3" in app.pl_frame.cget("text")
    print("1. 打开文件夹 OK：3 首已扫描，第 1 首加载，无 LRC 占位显示")

    # --- 2. 有修改 → 下一首时选"保存" → 保存并切换 + 自动加载新曲 LRC ---
    app.meta = {"ti": "临时歌曲"}
    app.lines = [LrcLine([123], "hello")]
    app._set_modified()
    app.file_path = os.path.join(tmp, "01.lrc")
    answers.append(True)                      # 选择"保存"
    app.next_track()
    saved = open(os.path.join(tmp, "01.lrc"), encoding="utf-8").read()
    assert "hello" in saved and "[ti:临时歌曲]" in saved, saved
    assert app.audio.loaded_path == p2 and app._pl_index == 1
    assert len(app.lines) == 2 and app.meta.get("ti") == "第二首"
    assert not app._modified
    assert not app.empty_state.place_info(), "有 LRC 后占位应隐藏"
    print("2. 切换保存确认(是) OK：01.lrc 已写出，02.lrc 已自动加载")

    # --- 3. 选"取消" → 留在本曲 ---
    app._set_modified()
    answers.append(None)
    app.next_track()
    assert app._pl_index == 1 and app.audio.loaded_path == p2 and app._modified
    print("3. 切换保存确认(取消) OK：留在本曲，修改保留")

    # --- 4. 选"否" → 放弃修改并切换；新曲无 LRC → 清空并显示占位 ---
    answers.append(False)
    app.next_track()
    assert app._pl_index == 2 and app.audio.loaded_path == p3
    assert not app.lines and not app._modified
    assert app.empty_state.place_info(), "03 无 LRC，应显示占位"
    print("4. 切换保存确认(否) OK：放弃修改切到第 3 首，无 LRC 占位显示")

    # --- 5. 循环切换 ---
    app.prev_track(); assert app._pl_index == 1
    app.prev_track(); assert app._pl_index == 0
    app.prev_track(); assert app._pl_index == 2 and app.audio.loaded_path == p3
    app.next_track(); assert app._pl_index == 0
    print("5. 上一首/下一首循环切换 OK")

    # --- 6. 列表双击切换（模拟） ---
    app.switch_track(2)
    assert app._pl_index == 2 and app.audio.loaded_path == p3
    assert app.pl_list.get(2).startswith("▶")
    print("6. 列表定位切换 OK")

    app.audio.stop(); app.audio.pygame.mixer.quit(); app.destroy()
    print("ALL PLAYLIST TESTS OK")


if __name__ == "__main__":
    main()
