#!/usr/bin/env python3
"""
每日自动更新小四门题目脚本
读取 question-bank.json，按章节进度选题，插入 review.html，更新 progress.json
在 GitHub Actions 中每日自动执行
"""
import json
import re
import os
import random
from datetime import datetime, timezone, timedelta

# 路径（相对于仓库根目录）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(SCRIPT_DIR)
BANK_PATH = os.path.join(REPO_DIR, "question-bank.json")
PROGRESS_PATH = os.path.join(REPO_DIR, "progress.json")
HTML_PATH = os.path.join(REPO_DIR, "review.html")

SUBJECTS = ["history", "geography", "biology", "politics"]
QUESTIONS_PER_SUBJECT = 5  # 每科每天5题（3选择+2填空）


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_beijing_date():
    """获取北京时间（UTC+8）的日期字符串"""
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).strftime("%Y-%m-%d")


def pick_questions(bank, subject, chapter_idx):
    """从题库中选取当前章节的5道题（3选择+2填空）"""
    chapters = bank[subject]["chapters"]
    chapter_name = chapters[chapter_idx]
    questions = bank[subject]["questions"][chapter_name]

    # 分离选择题和填空题
    choices = [q for q in questions if q["type"] == "choice"]
    fills = [q for q in questions if q["type"] == "fill"]

    # 选取3选择+2填空
    picked = choices[:3] + fills[:2]

    # 打乱顺序
    random.shuffle(picked)

    return picked, chapter_name


def generate_card_entry(card_id, subject, question):
    """生成一条卡片的JS对象字符串"""
    parts = [f"id:{card_id}", f"subject:'{subject}'", f"type:'{question['type']}'"]

    # 转义单引号
    front = question["front"].replace("'", "\\'")
    back = question["back"].replace("'", "\\'")
    parts.append(f"front:'{front}'")
    parts.append(f"back:'{back}'")

    if question["type"] == "choice":
        options = [opt.replace("'", "\\'") for opt in question["options"]]
        opts_str = ",".join(f"'{opt}'" for opt in options)
        parts.append(f"options:[{opts_str}]")
        parts.append(f"answerIndex:{question['answerIndex']}")
    else:
        fill_answer = question["fillAnswer"].replace("'", "\\'")
        parts.append(f"fillAnswer:'{fill_answer}'")

    parts.append("mastered:false")
    parts.append("reviewCount:0")
    parts.append("isSample:false")

    return "{" + ",".join(parts) + "}"


def insert_cards_into_html(html_content, new_cards_str):
    """将新卡片字符串插入到 HTML 的 SAMPLE_CARDS 数组末尾"""
    # 找到 SAMPLE_CARDS 数组的结束位置 ];
    # 使用正则匹配：从 var SAMPLE_CARDS=[ 开始到最后一个 ];
    pattern = r"(var SAMPLE_CARDS=\[.*?)(\];)"
    match = re.search(pattern, html_content, re.DOTALL)
    if not match:
        raise ValueError("无法找到 SAMPLE_CARDS 数组")

    before = match.group(1)
    after = match.group(2)

    # 确保 before 的最后一个字符是换行或逗号
    before_stripped = before.rstrip()
    if not before_stripped.endswith("[") and not before_stripped.endswith(","):
        before = before_stripped + ",\n"
    elif before_stripped.endswith("["):
        before = before_stripped + "\n"

    new_content = html_content[:match.start()] + before + new_cards_str + "\n" + after + html_content[match.end():]
    return new_content


def get_max_card_id(html_content):
    """从 HTML 中获取当前最大的 card id"""
    ids = re.findall(r"\{id:(\d+),", html_content)
    if not ids:
        return 0
    return max(int(id) for id in ids)


def main():
    print("=" * 60)
    print("小四门每日自动出题")
    print(f"北京时间: {get_beijing_date()}")
    print("=" * 60)

    # 加载题库和进度
    bank = load_json(BANK_PATH)
    progress = load_json(PROGRESS_PATH)

    # 加载 HTML
    with open(HTML_PATH, "r", encoding="utf-8") as f:
        html_content = f.read()

    # 获取当前最大 id
    max_id = get_max_card_id(html_content)
    print(f"当前最大 card id: {max_id}")

    # 为每科生成5道题
    all_new_cards = []
    today = get_beijing_date()

    for subject in SUBJECTS:
        chapter_idx = progress[subject]["chapterIndex"]
        questions, chapter_name = pick_questions(bank, subject, chapter_idx)
        print(f"\n{subject} - 章节[{chapter_idx}]: {chapter_name}")
        for q in questions:
            max_id += 1
            card_str = generate_card_entry(max_id, subject, q)
            all_new_cards.append(card_str)
            q_preview = q["front"][:30] + "..." if len(q["front"]) > 30 else q["front"]
            print(f"  id:{max_id} [{q['type']}] {q_preview}")

        # 更新进度：进入下一章
        next_idx = (chapter_idx + 1) % len(bank[subject]["chapters"])
        progress[subject]["chapterIndex"] = next_idx
        progress[subject]["totalAdded"] = progress[subject].get("totalAdded", 0) + len(questions)

    progress["lastRun"] = today

    # 生成插入字符串
    date_comment = f"/* --- {today} 每日自动更新：四科各5题 --- */"
    new_cards_str = date_comment + "\n" + ",\n".join(all_new_cards)

    # 插入到 HTML
    print(f"\n插入 {len(all_new_cards)} 张新卡片到 review.html...")
    new_html = insert_cards_into_html(html_content, new_cards_str)

    # 验证
    new_max_id = get_max_card_id(new_html)
    print(f"更新后最大 card id: {new_max_id}")

    # 保存 HTML
    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(new_html)
    print("review.html 已更新")

    # 保存进度
    save_json(PROGRESS_PATH, progress)
    print("progress.json 已更新")

    # 输出摘要
    print("\n" + "=" * 60)
    print("更新完成！")
    print(f"日期: {today}")
    print(f"新增卡片: {len(all_new_cards)} 张 (id {max_id - len(all_new_cards) + 1}-{max_id})")
    for subject in SUBJECTS:
        idx = progress[subject]["chapterIndex"]
        ch = bank[subject]["chapters"][idx]
        print(f"  {subject}: 下次章节[{idx}]={ch}, 累计{progress[subject]['totalAdded']}题")
    print("=" * 60)


if __name__ == "__main__":
    main()
