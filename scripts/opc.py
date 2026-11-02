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
  ack                  归档待裁决（原文保留，只是不再计入待办）
  status               打印公司现状
  build                从状态生成自包含的 dashboard.html
  serve                本地起服务，浏览器里直接发话、归档（真写入）
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
    "BOSS":     ("老板指令", "group"),
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
    pend_ids = {m["id"] for m in pend}
    archived = sum(
        1 for m in msgs
        if m["channel"] != "group"
        and m["kind"] in ("CHALLENGE", "RISK", "DECIDE")
        and m["id"] not in pend_ids
    )
    print("待裁决：%d 条" % len(pend))
    for p in pend:
        print("  · %s [%s] %s" % (p["from"], KINDS[p["kind"]][0], p["text"][:50]))
    print("已归档：%d 条（原文仍在私聊记录里）" % archived)
    return 0


def pending_decisions(msgs):
    """待老板拍板的事。

    一条私聊消息算待办，需同时满足：
      1. 类型是 CHALLENGE / RISK / DECIDE
      2. 没被显式归档（handled）
      3. 同通道内它之后没有出现过 DECISION

    第 3 条兼容早期数据：老消息没有 handled 字段，靠裁决自动闭环。
    """
    out = []
    per_channel = {}
    for i, m in enumerate(msgs):
        if m["channel"] == "group":
            continue
        per_channel.setdefault(m["channel"], []).append((i, m))
    for ch, items in per_channel.items():
        last_decision = -1
        for i, m in items:
            if m["kind"] == "DECISION":
                last_decision = i
        for i, m in items:
            if m["kind"] in ("CHALLENGE", "RISK", "DECIDE") and not m.get("handled") and i > last_decision:
                out.append(m)
    return out


# ---------------------------------------------------------------- ack

def cmd_ack(args):
    root = Path(args.dir).resolve()
    data = load(messages_path(root), {"seq": 0, "items": []})
    pend = {m["id"] for m in pending_decisions(data["items"])}

    if not args.id and not (args.channel and args.all):
        print("用法：opc ack --id M020 [--id M027]")
        print("      opc ack --channel dm:qa --all")
        return 2

    if not pend:
        print("没有待裁决的事，不用归档。")
        return 0

    count = 0
    hit_ids = []
    for m in data["items"]:
        if m["id"] not in pend:
            continue
        hit = m["id"] in args.id if args.id else (args.all and m["channel"] == args.channel)
        if not hit:
            continue
        m["handled"] = True
        m["handled_at"] = now()
        if args.reason:
            m["handled_note"] = args.reason
        count += 1
        hit_ids.append(m["id"])

    if not count:
        print("没有匹配的待裁决条目。当前待办：%s" % "、".join(sorted(pend)))
        return 1

    save(messages_path(root), data)
    print("已归档 %d 条：%s" % (count, "、".join(hit_ids)))
    print("注意：归档不是删除，原文仍在对应员工的私聊记录里，只是不再计入待办。")
    left = pending_decisions(data["items"])
    print("剩余待裁决：%d 条" % len(left))
    return 0


# ---------------------------------------------------------------- build

def build_payload(root):
    c = load(company_path(root), None)
    tasks = load(tasks_path(root), {"seq": 0, "items": []})["items"]
    msgs = load(messages_path(root), {"seq": 0, "items": []})["items"]
    return {
        "company": c,
        "tasks": tasks,
        "messages": msgs,
        "kinds": {k: v[0] for k, v in KINDS.items()},
        "pending": [m["id"] for m in pending_decisions(msgs)],
        "generated": now(),
    }


def render_html(root):
    tpl_path = Path(__file__).resolve().parent.parent / "assets" / "dashboard_template.html"
    if not tpl_path.exists():
        raise FileNotFoundError("缺模板：%s" % tpl_path)
    tpl = tpl_path.read_text(encoding="utf-8")
    payload = build_payload(root)
    return tpl.replace("/*__OPC_DATA__*/", json.dumps(payload, ensure_ascii=False))


def cmd_build(args):
    root = Path(args.dir).resolve()
    if not company_path(root).exists():
        print("公司还没初始化，先跑 opc init")
        return 1
    try:
        html = render_html(root)
    except FileNotFoundError as e:
        print(e)
        return 1
    out = opc_dir(root) / "dashboard.html"
    out.write_text(html, encoding="utf-8")
    print("工作台已生成：%s" % out)
    print("想直接在浏览器里用（输入框真的能写入）：opc serve --open")
    return 0


# ---------------------------------------------------------------- serve

def probe_existing(root, base_port, span=12):
    """看看这台机器上是不是已经有一份本公司在跑的服务，有就直接复用。"""
    import urllib.request
    for p in range(base_port, base_port + span):
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/api/ping" % p, timeout=0.4) as r:
                d = json.loads(r.read().decode("utf-8"))
            if d.get("ok") and d.get("company") == root.name:
                return "http://127.0.0.1:%d/" % p
        except Exception:
            continue
    return None


def cmd_serve(args):
    """本地起一个小服务，让工作台真正可写。

    只监听 127.0.0.1，不对外、不需要鉴权、不开防火墙。
    """
    import threading
    import webbrowser
    from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

    root = Path(args.dir).resolve()
    if not company_path(root).exists():
        print("公司还没初始化，先跑 opc init")
        return 1

    if args.open:
        existing = probe_existing(root, args.port)
        if existing:
            print("工作台已经在运行：%s" % existing)
            print("已在默认浏览器中打开，没有重复起服务。")
            webbrowser.open(existing)
            return 0

    def append_message(channel, kind, text, sender="boss"):
        data = load(messages_path(root), {"seq": 0, "items": []})
        data["seq"] += 1
        data["items"].append({
            "id": "M%03d" % data["seq"],
            "ts": now(),
            "channel": channel,
            "from": sender,
            "kind": kind,
            "task": "",
            "text": text,
        })
        save(messages_path(root), data)
        return data["items"][-1]["id"]

    def mark_handled(ids):
        data = load(messages_path(root), {"seq": 0, "items": []})
        pend = {m["id"] for m in pending_decisions(data["items"])}
        n = 0
        for m in data["items"]:
            if m["id"] in pend and m["id"] in ids:
                m["handled"] = True
                m["handled_at"] = now()
                n += 1
        save(messages_path(root), data)
        return n

    class Handler(BaseHTTPRequestHandler):
        server_version = "opc/1.2"

        def log_message(self, fmt, *a):
            pass

        def _send(self, body, ctype, code=200):
            raw = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def _json(self, obj, code=200):
            self._send(json.dumps(obj, ensure_ascii=False), "application/json; charset=utf-8", code)

        def do_GET(self):
            path = self.path.split("?")[0]
            if path in ("/", "/index.html"):
                try:
                    self._send(render_html(root), "text/html; charset=utf-8")
                except Exception as e:
                    self._send("<pre>%s</pre>" % e, "text/html; charset=utf-8", 500)
            elif path == "/api/state":
                self._json(build_payload(root))
            elif path == "/api/ping":
                self._json({"ok": True, "company": root.name})
            else:
                self._send("not found", "text/plain; charset=utf-8", 404)

        def do_POST(self):
            path = self.path.split("?")[0]
            try:
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}")
            except Exception:
                self._json({"ok": False, "error": "bad json"}, 400)
                return

            if path == "/api/msg":
                channel = (body.get("channel") or "").strip()
                kind = (body.get("kind") or "").strip().upper()
                text = (body.get("text") or "").strip()
                if channel not in ("group",) and not channel.startswith("dm:"):
                    self._json({"ok": False, "error": "channel 非法"}, 400)
                    return
                if kind not in KINDS or kind in ("TASK", "PROGRESS", "DELIVER"):
                    self._json({"ok": False, "error": "工作台只能发 BOSS / DECISION 类消息"}, 400)
                    return
                if not text:
                    self._json({"ok": False, "error": "内容为空"}, 400)
                    return
                mid = append_message(channel, kind, text)
                self._json({"ok": True, "id": mid, "state": build_payload(root)})

            elif path == "/api/ack":
                ids = body.get("ids") or []
                if isinstance(ids, str):
                    ids = [ids]
                n = mark_handled(set(ids))
                self._json({"ok": True, "handled": n, "state": build_payload(root)})

            else:
                self._json({"ok": False, "error": "not found"}, 404)

    port = args.port
    srv = None
    for p in range(port, port + 12):
        try:
            srv = ThreadingHTTPServer(("127.0.0.1", p), Handler)
            port = p
            break
        except OSError:
            continue
    if srv is None:
        print("端口 %d 起都被占用，换个 --port 试试" % args.port)
        return 1

    url = "http://127.0.0.1:%d/" % port
    print("工作台已启动：%s" % url)
    print("公司：%s" % root.name)
    print("这个服务只监听本机，关掉窗口或按 Ctrl+C 就停。输入框和归档按钮会真的写入 .opc/。")
    if args.open:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        srv.server_close()
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

    p = sub.add_parser("ack", help="归档待裁决（不删除原文）")
    p.add_argument("--id", action="append", default=[], help="消息编号，可重复")
    p.add_argument("--channel", default="", help="dm:<代号>，配合 --all 使用")
    p.add_argument("--all", action="store_true", help="归档该通道全部待裁决")
    p.add_argument("--reason", default="", help="归档理由")
    p.set_defaults(func=cmd_ack)

    p = sub.add_parser("build", help="生成工作台")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("serve", help="本地起工作台服务，输入框真的能写入")
    p.add_argument("--port", type=int, default=8765, help="起始端口，默认 8765，被占用会自动往后找")
    p.add_argument("--open", action="store_true", help="启动后自动用默认浏览器打开")
    p.set_defaults(func=cmd_serve)

    args = ap.parse_args()
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
