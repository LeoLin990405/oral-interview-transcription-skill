#!/usr/bin/env python3
"""
oral-history-master 单元测试（stdlib unittest，零依赖）
跑法：  cd oral-history-master && python3 -m unittest discover tests
或：     python3 tests/test_pipeline.py
覆盖最易错的确定性逻辑：术语解析 / 数字归一 / 分块边界与说话人延续 /
说话人识别与合并 / 忠实度启发式。语义层不在单测范围（由 quality-guard 人工审）。
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import config as C          # noqa: E402
import chunker              # noqa: E402
import fidelity_checker as F  # noqa: E402
import transcript_ingest as T  # noqa: E402
import glossary_extractor as G  # noqa: E402
import review_diff as R     # noqa: E402
import filler_scan as FS    # noqa: E402
import package_review as P  # noqa: E402


class TestConfig(unittest.TestCase):
    def test_parse_term_lock(self):
        md = (
            "| 规范写法 | 变体/别名 | 类别 | 备注 |\n"
            "|---|---|---|---|\n"
            "| 中科院半导体所 | 半导体所；中科院半导体研究所 | 机构 | x |\n"
            "| 863计划 | 八六三；八六三计划 | 项目 |  |\n"
        )
        p = Path("/tmp/_oh_tl_test.md"); p.write_text(md, encoding="utf-8")
        rows = C.parse_term_lock(p)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["canonical"], "中科院半导体所")
        self.assertIn("半导体所", rows[0]["variants"])
        self.assertIn("八六三", rows[1]["variants"])

    def test_extract_numbers(self):
        self.assertEqual(C.extract_number_values("一九五九年"), {"1959"})
        self.assertEqual(C.extract_number_values("1943 年"), {"1943"})
        self.assertEqual(C.extract_number_values("六二年"), {"62"})
        self.assertIn("23", C.extract_number_values("二十三个人"))
        self.assertEqual(C.extract_number_values("我去了一个地方"), set())  # 单字不抽

    def test_chunk_body(self):
        txt = (f"<!-- chunk_001 -->\n\n{C.CHUNK_OVERLAP_HEAD}\n上文回顾内容。\n\n"
               f"{C.CHUNK_BODY_HEAD}\n\n【受访人】这是正文。")
        self.assertEqual(C.chunk_body(txt), "【受访人】这是正文。")
        self.assertNotIn("上文回顾", C.chunk_body(txt))

    def test_parse_switches(self):
        md = (
            "| 开关 | 取值 |\n"
            "|---|---|\n"
            "| genre（文类） | 播客 |\n"
            "| fillers（语气词） | 加强 |\n"
            "| fidelity（仿真度） | 中 |\n"
        )
        p = Path("/tmp/_oh_sw_test.md"); p.write_text(md, encoding="utf-8")
        sw = C.parse_switches(p)
        self.assertEqual(sw["genre"], "播客")
        self.assertEqual(sw["fillers"], "加强")
        self.assertEqual(sw["fidelity"], "中")
        self.assertEqual(sw["dialect"], "保留")  # 缺省
        self.assertEqual(C.parse_switches(Path("/tmp/_oh_missing_switches.md"))["genre"], "口述史")
        self.assertTrue(C.is_oral_genre("口述史"))
        self.assertFalse(C.is_oral_genre("播客"))
        self.assertEqual(C.canon_speaker("问"), "采访人")
        self.assertEqual(C.canon_speaker("嘉宾"), "受访人")


class TestChunker(unittest.TestCase):
    def test_split_sentences(self):
        self.assertEqual(len(chunker.split_sentences("第一句。第二句！第三句？")), 3)

    def test_chunk_units_label_continuity(self):
        unit = "【受访人】" + "甲" * 200 + "。" + "乙" * 200 + "。" + "丙" * 200 + "。"
        chunks = chunker.chunk_units([unit], target=150, hard_max=250)
        self.assertGreaterEqual(len(chunks), 2)
        # 首块带原标签；续块补回 （续）
        self.assertTrue(chunks[0][0].startswith("【受访人】"))
        self.assertTrue(any("【受访人】（续）" in c[0] for c in chunks[1:]))

    def test_chunk_units_respects_target(self):
        units = ["【受访人】" + "字" * 100 for _ in range(5)]
        chunks = chunker.chunk_units(units, target=250, hard_max=400)
        self.assertGreater(len(chunks), 1)  # 5×~105 字必然多块


class TestIngest(unittest.TestCase):
    def test_speaker_detect_and_merge(self):
        raw = "受访人：你好。\n采访人：嗯。\n受访人：再说一句。\n受访人：还有一句。"
        blocks = T._segment(T._normalize(raw))
        self.assertTrue(blocks[0].startswith("【受访人】"))
        self.assertTrue(blocks[1].startswith("【采访人】"))
        # 末尾两条同为受访人 → 合并成一块
        self.assertEqual(sum(1 for b in blocks if b.startswith("【受访人】")), 2)
        self.assertIn("再说一句。 还有一句。", blocks[-1])

    def test_name_role_and_speaker_formats(self):
        self.assertEqual(T._detect_speaker("李某某（受访人）：内容")[0], "受访人")
        self.assertEqual(T._detect_speaker("问：你做什么？")[0], "采访人")
        self.assertEqual(T._detect_speaker("说话人1：内容")[0], "说话人1")  # 未知标签原样保留
        self.assertEqual(T._detect_speaker("主持：欢迎回来")[0], "主持")
        self.assertEqual(T._detect_speaker("嘉宾：大家好")[0], "嘉宾")
        self.assertEqual(T._detect_speaker("李华（嘉宾）：内容")[0], "嘉宾")

    def test_timestamp_and_inaudible(self):
        blocks = T._segment(T._normalize("[00:12:34] 受访人：那个[听不清]事。"))
        self.assertIn("〔时间 00:12:34〕", blocks[0])
        self.assertIn("【录音不清】", blocks[0])


class TestFidelity(unittest.TestCase):
    def test_num_is_new(self):
        self.assertFalse(F._num_is_new("1962", {"62"}))    # 年份补全，不算新增
        self.assertFalse(F._num_is_new("59", {"1959"}))
        self.assertTrue(F._num_is_new("1947", {"1943"}))   # 真·新增 → flag

    def test_entities(self):
        ents = F._entities("我在中科院半导体研究所，郑所长很照顾")
        self.assertIn("中科院半导体研究所", ents)
        self.assertIn("郑", ents)  # 称谓锚定


class TestGlossary(unittest.TestCase):
    def test_clean_candidate(self):
        self.assertEqual(G._clean_candidate("我们那个课题组"), "课题组")
        self.assertIsNone(G._clean_candidate("您是哪一年到所"))  # 含停用字 → 丢弃

    def test_cluster_containment(self):
        cands = [{"term": "半导体所", "kind": "机构"},
                 {"term": "中科院半导体所", "kind": "机构"},
                 {"term": "课题组", "kind": "机构"}]
        clusters = G._cluster(cands)
        grp = next(c for c in clusters if "半导体所" in c)
        self.assertIn("中科院半导体所", grp)        # 子串 → 同组
        self.assertTrue(any(c == ["课题组"] for c in clusters))  # 无关 → 独立


class TestReviewDiff(unittest.TestCase):
    def test_split_turns_and_align(self):
        orig = "【采访人】嗯，您哪年来的？\n\n【受访人】我是，我是五九年到的。"
        edited = "【问】您哪年来的？\n\n【受访人】我是一九五九年到的。"
        turns = R.split_turns(orig)
        self.assertEqual([t.speaker for t in turns], ["采访人", "受访人"])
        aligned = R.build_aligned(orig, edited)
        self.assertEqual(len(aligned), 2)
        self.assertEqual(aligned[0].label(), "【采访人】→【问】")
        self.assertTrue(aligned[0].changed)
        self.assertIn("嗯", aligned[0].orig)
        self.assertTrue(any(tag == "delete" and "我是" in a for tag, a, _ in aligned[1].ops)
                        or aligned[1].deleted_chars > 0)

    def test_diff_body_strips_timestamp_and_unifies_quotes(self):
        self.assertEqual(R.diff_body("00:01 嗯，我是"), "嗯，我是")
        self.assertEqual(R.diff_body("〔时间 00:01〕我是"), "我是")
        self.assertEqual(R.diff_body("叫“吃皇粮”"), R.diff_body('叫"吃皇粮"'))

    def test_empty_inputs(self):
        self.assertEqual(R.split_turns(""), [])
        self.assertEqual(R.build_aligned("", ""), [])

    def test_html_escapes_markup(self):
        html = R.redline_html(R.char_ops("<script>x</script>", "x"))
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>", html)

    def test_notes_become_comments_not_insertions(self):
        orig = "我是五九年到的。"
        edited = "我是一九五九年到的。〔口误纠正：取最终值〕"
        t = R.build_aligned(orig, edited)[0]
        self.assertTrue(any("口误纠正" in n for n in t.notes))
        self.assertNotIn("口误纠正", t.edited_clean)
        md = R.redline_markdown(t.ops)
        self.assertNotIn("口误纠正", md)

    def test_redline_marks_delete_and_insert(self):
        ops = R.char_ops("嗯我是五九年", "我是一九五九年")
        md = R.redline_markdown(ops)
        self.assertIn("~~", md)
        self.assertIn("**", md)
        html = R.redline_html(ops)
        self.assertIn("<del>", html)
        self.assertIn("<ins>", html)

    def test_write_review_bundle(self):
        root = Path("/tmp/_oh_review_demo")
        if root.exists():
            import shutil
            shutil.rmtree(root)
        C.ensure_layout(root)
        chunk = (
            f"<!-- chunk_001 -->\n\n{C.CHUNK_OVERLAP_HEAD}\n上文。\n\n"
            f"{C.CHUNK_BODY_HEAD}\n\n【受访人】嗯，我是，我是五九年到的。"
        )
        (root / C.PROJECT_LAYOUT["chunks"] / "chunk_001.md").write_text(chunk, encoding="utf-8")
        (root / C.PROJECT_LAYOUT["edited"] / "chunk_001.edited.md").write_text(
            "【受访人】我是一九五九年到的。", encoding="utf-8")
        paths = R.write_review_bundle(root, title="tmp")
        self.assertTrue(paths["md"].exists())
        self.assertTrue(paths["html"].exists())
        self.assertTrue(paths["docx"].exists())
        html = paths["html"].read_text(encoding="utf-8")
        self.assertIn("<del>", html)
        self.assertIn("审阅", html)
        self.assertGreater(paths["docx"].stat().st_size, 200)
        # docx 是合法 zip
        import zipfile
        with zipfile.ZipFile(paths["docx"]) as z:
            self.assertIn("word/document.xml", z.namelist())
            xml = z.read("word/document.xml").decode("utf-8")
            self.assertIn("<w:del", xml)
            self.assertIn("<w:ins", xml)
        again = R.write_review_bundle(root, title="tmp")
        self.assertEqual(paths["docx"].read_bytes(), again["docx"].read_bytes())


class TestFillerScan(unittest.TestCase):
    def test_flags_leftover_fillers_and_stutter(self):
        text = "嗯，那个，我是，我是后来才知道的。就是说所里定了。"
        hits = FS._hits_for(text, strong=False)
        kinds = {k for k, _ in hits}
        self.assertIn("语气词", kinds)
        self.assertIn("口头禅", kinds)
        self.assertIn("自我重复", kinds)

    def test_functional_particle_not_flagged(self):
        hits = FS._hits_for("困难啊，设备差。", strong=False)
        self.assertFalse(any(kind == "语气词" and excerpt == "啊" for kind, excerpt in hits))
        isolated = FS._hits_for("啊，我后来才知道。", strong=False)
        self.assertTrue(any(kind == "语气词" for kind, _ in isolated))


class TestPackageReview(unittest.TestCase):
    def test_delivery_banner_by_genre(self):
        oral = P.delivery_banner("口述史", 2)
        pod = P.delivery_banner("播客", 0)
        self.assertIn("须经受访人审阅签字", oral)
        self.assertIn("播客整理稿", pod)
        self.assertNotIn("签字", pod)


if __name__ == "__main__":
    unittest.main(verbosity=2)
