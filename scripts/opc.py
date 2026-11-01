#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""opc - One-person company 状态内核

用工作区 .opc/ 目录下的 JSON 文件作为唯一事实来源。
不联网、不需要 API Key、不依赖第三方包。

子命令：
  init                 初始化公司
  msg                  追加一条群聊/私聊消息
  task add|set|list    任务派发与进度
  gate                 门禁判定
  phase                更新当前阶段
  status               打印公司现状
  build                从状态生成自包含的 dashboard.html
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROSTER = [
    ("pm",   "项目经理", "Project Manager", "reasoning", "项", "teal"),
    ("pd",   "产品经理", "Product Manager", "default",   "产", "blue"),
    ("ui",   "UI设计",   "UI Designer",     "default",   "U",  "pink"),
    ("arch", "架构师",   "Architect",       "reasoning", "架", "purple"),
    ("dev",  "程序员",   "Engineer",        "default",   "码", "green"),
    ("qa",   "测试",     "QA",              "lite",      "测", "amber"),
    ("ops",  "运维",     "Ops",             "lite",      "运", "coral"),
]

PHASES = [
    "第 1 步 · 提出需求",
    "第 2 步 · 项目启动",
    "第 3 步 · 需求分析（粗）",
    "第 4 步 · 确认方案",
    "第 5 步 · 需求分析（细）",
    "第 6 步 · 原型图设计 / 业务设计",
    "第 7 步 · 编码实现",
    "第 8 步 · 软件测试",
    "第 9 步 · 部署运行",
]

KINDS = {
    "TASK":     ("派活",   "group"),
    "PROGRESS": ("进度",   "group"),
    "DELIVER":  ("交付",   "group"),
    "CHALLENGE":("方案分歧", "dm"),
    "RISK":     ("风险预警", "dm"),
    "DECIDE":   ("请求裁决", "dm"),
    "DECISION": ("老板裁决", "dm"),
}


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def opc_dir(root):
    return Path(root) / ".opc"


def load(path, default):
    p = Path(path)
    if not p.exists():
        return default
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def save(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def company_path(root):
    return opc_dir(root) / "company.json"


def tasks_path(root):
    return opc_dir(root) / "tasks.json"


def messages_path(root):
    return opc_dir(root) / "messages.json"


# ---------------------------------------------------------------- init

def cmd_init(args):
    root = Path(args.dir).resolve()
    d = opc_dir(root)
    if company_path(root).exists() and not args.force:
        print("公司已存在：%s（加 --force 可重建）" % d)
        return 0

    employees = [
        {
            "id": eid, "name": name, "role": role, "tier": tier,
            "avatar": av, "color": color,
        }
        for eid, name, role, tier, av, color in ROSTER
    ]
    save(company_path(root), {
        "name": root.name or "One-person company",
        "created": now(),
        "phase": PHASES[0],
        "boss": "老板",
        "employees": employees,
    })
    save(tasks_path(root), {"seq": 0, "items": []})
    save(messages_path(root), {"seq": 0, "items": []})
    (d / "docs").mkdir(parents=True, exist_ok=True)

    print("公司已开张：%s" % d)
    print("员工 %d 人：%s" % (len(employees), "、".join(e["name"] for e in employees)))
    print("下一步：opc task add / opc msg / opc build")
    return 0


# ---------------------------------------------------------------- msg

def cmd_msg(args):
    root = Path(args.dir).resolve()
    data = load(messages_path(root), {"seq": 0, "items": []})

    kind = args.kind.upper()
    if kind not in KINDS:
        print("未知类型 %s，可用：%s" % (kind, "、".join(KINDS)))
        return 2

    channel = args.channel
    if channel not in ("group",) and not channel.startswith("dm:"):
        print("channel 只能是 group 或 dm:<员工代号>")
        return 2

    who = args.sender
    if who != "boss":
        ids = {e[0] for e in ROSTER}
        if who not in ids:
            print("未知员工代号 %s，可用：boss、%s" % (who, "、".join(sorted(ids))))
            return 2

    data["seq"] += 1
    item = {
        "id": "M%03d" % data["seq"],
        "ts": now(),
        "channel": channel,
        "from": who,
        "kind": kind,
        "task": args.task or "",
        "text": args.text,
    }
    data["items"].append(item)
    save(messages_path(root), data)
    label = KINDS[kind][0]
    print("[%s] %s → %s：%s" % (channel, who, label, args.text[:60]))
    return 0


# ---------------------------------------------------------------- task

def cmd_task(args):
    root = Path(args.dir).resolve()
    data = load(tasks_path(root), {"seq": 0, "items": []})

    if args.action == "add":
        data["seq"] += 1
        tid = "T-%03d" % data["seq"]
        data["items"].append({
            "id": tid,
            "title": args.title,
            "owner": args.owner,
            "phase": args.phase or "",
            "status": "todo",
            "progress": 0,
            "artifacts": [],
            "gate": None,
            "created": now(),
            "updated": now(),
        })
        save(tasks_path(root), data)
        print("已派活 %s → %s：%s" % (tid, args.owner, args.title))
        return 0

    if args.action == "set":
        if not args.id:
            print("需要 --id")
            return 2
        for t in data["items"]:
            if t["id"] == args.id:
                if args.status:
                    t["status"] = args.status
                    if args.status == "done" and not args.progress:
                        t["progress"] = 100
                if args.progress is not None:
                    t["progress"] = args.progress
                if args.artifact:
                    t["artifacts"].append(args.artifact)
                t["updated"] = now()
                save(tasks_path(root), data)
                print("%s 已更新：%s %d%%" % (t["id"], t["status"], t["progress"]))
                return 0
        print("找不到任务 %s" % args.id)
        return 1

    if args.action == "list":
        if not data["items"]:
            print("还没有任务。")
            return 0
        print("%-7s %-8s %-6s %4s  %s" % ("编号", "负责人", "状态", "进度", "标题"))
        for t in data["items"]:
            print("%-7s %-8s %-6s %3d%%  %s" % (
                t["id"], t["owner"], t["status"], t["progress"], t["title"]))
        return 0

    print("action 只能是 add / set / list")
    return 2


# ---------------------------------------------------------------- gate

def cmd_gate(args):
    root = Path(args.dir).resolve()
    data = load(tasks_path(root), {"seq": 0, "items": []})
    for t in data["items"]:
        if t["id"] == args.id:
            t["gate"] = {"result": args.result, "reason": args.reason or "", "ts": now()}
            if args.result == "pass":
                t["status"] = "done"
                t["progress"] = 100
            else:
                t["status"] = "doing"
            t["updated"] = now()
            save(tasks_path(root), data)
            mark = "通过" if args.result == "pass" else "打回"
            print("门禁%s：%s  %s" % (mark, t["id"], args.reason or ""))
            return 0
    print("找不到任务 %s" % args.id)
    return 1


# ---------------------------------------------------------------- phase

def cmd_phase(args):
    root = Path(args.dir).resolve()
    c = load(company_path(root), None)
    if not c:
        print("公司还没初始化，先跑 opc init")
        return 1
    if args.name:
        c["phase"] = args.name
        save(company_path(root), c)
        print("当前阶段：%s" % args.name)
    else:
        print("当前阶段：%s" % c.get("phase", ""))
        print("可选：")
        for p in PHASES:
            print("  " + p)
    return 0


# ---------------------------------------------------------------- status

def cmd_status(args):
    root = Path(args.dir).resolve()
    c = load(company_path(root), None)
    if not c:
        print("公司还没初始化，先跑 opc init")
        return 1
    tasks = load(tasks_path(root), {"seq": 0, "items": []})["items"]
    msgs = load(messages_path(root), {"seq": 0, "items": []})["items"]

    print("公司：%s" % c.get("name"))
    print("阶段：%s" % c.get("phase"))
    done = sum(1 for t in tasks if t["status"] == "done")
    doing = sum(1 for t in tasks if t["status"] == "doing")
    print("任务：%d 个（完成 %d / 进行 %d / 待办 %d）" % (
        len(tasks), done, doing, len(tasks) - done - doing))
    print("消息：群聊 %d 条 / 私聊 %d 条" % (
        sum(1 for m in msgs if m["channel"] == "group"),
        sum(1 for m in msgs if m["channel"] != "group")))
    pend = pending_decisions(msgs)
    print("待裁决：%d 条" % len(pend))
    for p in pend:
        print("  · %s [%s] %s" % (p["from"], KINDS[p["kind"]][0], p["text"][:50]))
    return 0


def pending_decisions(msgs):
    """每个私聊线程里，最后一条 DECISION 之后的 CHALLENGE/RISK/DECIDE 都算待处理。"""
    out = []
    per_channel = {}
    for m in msgs:
        if m["channel"] == "group":
            continue
        per_channel.setdefault(m["channel"], []).append(m)
    for ch, items in per_channel.items():
        last_decision = -1
        for i, m in enumerate(items):
            if m["kind"] == "DECISION":
                last_decision = i
        for m in items[last_decision + 1:]:
            if m["kind"] in ("CHALLENGE", "RISK", "DECIDE"):
                out.append(m)
    return out


# ---------------------------------------------------------------- build

def cmd_build(args):
    root = Path(args.dir).resolve()
    c = load(company_path(root), None)
    if not c:
        print("公司还没初始化，先跑 opc init")
        return 1

    tasks = load(tasks_path(root), {"seq": 0, "items": []})["items"]
    msgs = load(messages_path(root), {"seq": 0, "items": []})["items"]

    tpl_path = Path(__file__).resolve().parent.parent / "assets" / "dashboard_template.html"
    if not tpl_path.exists():
        print("缺模板：%s" % tpl_path)
        return 1
    tpl = tpl_path.read_text(encoding="utf-8")

    payload = {
        "company": c,
        "tasks": tasks,
        "messages": msgs,
        "kinds": {k: v[0] for k, v in KINDS.items()},
        "pending": [m["id"] for m in pending_decisions(msgs)],
        "generated": now(),
    }
    html = tpl.replace("/*__OPC_DATA__*/", json.dumps(payload, ensure_ascii=False))
    out = opc_dir(root) / "dashboard.html"
    out.write_text(html, encoding="utf-8")
    print("工作台已生成：%s" % out)
    print("用法：打开它就能看到群聊和每个人的对话框。")
    return 0


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(prog="opc", description="One-person company 状态内核")
    ap.add_argument("--dir", default=".", help="项目根目录，默认当前目录")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="初始化公司")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("msg", help="追加消息")
    p.add_argument("--channel", required=True, help="group 或 dm:<代号>")
    p.add_argument("--sender", required=True, help="员工代号或 boss")
    p.add_argument("--kind", required=True, help="TASK/PROGRESS/DELIVER/CHALLENGE/RISK/DECIDE/DECISION")
    p.add_argument("--text", required=True)
    p.add_argument("--task", default="")
    p.set_defaults(func=cmd_msg)

    p = sub.add_parser("task", help="任务")
    p.add_argument("action", choices=["add", "set", "list"])
    p.add_argument("--title", default="")
    p.add_argument("--owner", default="")
    p.add_argument("--phase", default="")
    p.add_argument("--id", default="")
    p.add_argument("--status", default="")
    p.add_argument("--progress", type=int, default=None)
    p.add_argument("--artifact", default="")
    p.set_defaults(func=cmd_task)

    p = sub.add_parser("gate", help="门禁判定")
    p.add_argument("--id", required=True)
    p.add_argument("--result", required=True, choices=["pass", "reject"])
    p.add_argument("--reason", default="")
    p.set_defaults(func=cmd_gate)

    p = sub.add_parser("phase", help="阶段")
    p.add_argument("name", nargs="?", default="")
    p.set_defaults(func=cmd_phase)

    p = sub.add_parser("status", help="现状")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("build", help="生成工作台")
    p.set_defaults(func=cmd_build)

    args = ap.parse_args()
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
