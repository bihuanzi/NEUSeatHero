"""
总控台 - 统一管理 MOOC检测 和 NEU选位监控
首次运行强制配置，后续通过菜单选择启用的功能
"""
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).parent

# ========== 配置检查 ==========
def check_first_run():
    """检查是否首次运行（关键配置不存在）"""
    required = [
        ("config/notify", "SMTP邮件通知"),
        ("config/aimLesson", "MOOC课程URL"),
    ]
    missing = []
    for path, desc in required:
        p = HERE / path
        if not p.exists() or not _has_content(p):
            missing.append((path, desc))
    return missing

def _has_content(path):
    """文件存在且有实际内容（非纯注释）"""
    if not path.exists():
        return False
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            return True
    return False

def check_feature_ready(feature):
    """检查某个功能是否配置就绪"""
    checks = {
        "mooc": ["config/cookie", "config/aimLesson"],
        "seat": ["config/mathe_auth", "config/mathe_target"],
    }
    for path in checks.get(feature, []):
        p = HERE / path
        if not _has_content(p):
            return False
    return True

# ========== 设置向导 ==========
def setup_wizard():
    """首次运行设置向导"""
    print("\n" + "=" * 55)
    print("  欢迎使用 pram_lifecontroler 总控台")
    print("=" * 55)
    print("\n首次运行需要配置以下内容：\n")

    steps = [
        ("SMTP邮件通知", "config/notify",
         "填入QQ邮箱和SMTP授权码\n  格式: smtp_server=smtp.qq.com\n        sender=你的QQ@qq.com\n        password=授权码\n        to=接收邮箱@qq.com"),
        ("MOOC课程URL", "config/aimLesson",
         "填入中国大学MOOC课程链接\n  格式: https://www.icourse163.org/learn/NEU-1001638002?tid=1476488478"),
    ]

    for name, path, hint in steps:
        print(f"  [{name}] → 编辑 {path}")
        print(f"  {hint}")
        full_path = HERE / path
        if not full_path.exists():
            full_path.write_text("", encoding='utf-8')

        print(f"\n  请在编辑器中填写 {path}，完成后按回车继续...")
        input()

    print("\n  ✅ 基础配置完成！")
    print("  后续可通过菜单补充其他配置（MOOC Cookie、选位认证等）\n")

# ========== 交互菜单 ==========
def load_settings():
    """加载功能开关"""
    path = HERE / "config" / "settings"
    if not path.exists():
        return {}
    cfg = {}
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        line = line.strip()
        if '=' in line and not line.startswith('#'):
            k, _, v = line.partition('=')
            cfg[k.strip()] = v.strip().lower() == 'true'
    return cfg

def save_settings(settings):
    """保存功能开关"""
    path = HERE / "config" / "settings"
    lines = ["# 功能开关 true=启用 false=禁用"]
    for k, v in settings.items():
        lines.append(f"{k}={'true' if v else 'false'}")
    path.write_text("\n".join(lines), encoding='utf-8')

def show_menu(settings):
    """显示交互菜单，返回用户选择"""
    mooc_ready = check_feature_ready("mooc")
    seat_ready = check_feature_ready("seat")

    mooc_on = settings.get("mooc", True)
    seat_on = settings.get("seat", True)

    while True:
        print("\n" + "=" * 45)
        print("  pram_lifecontroler 总控台")
        print("=" * 45)

        mooc_status = "✅" if (mooc_on and mooc_ready) else ("⚠未配置" if mooc_on else "⏸ 已暂停")
        seat_status = "✅" if (seat_on and seat_ready) else ("⚠未配置" if seat_on else "⏸ 已暂停")
        print(f"  [1] MOOC作业检测   {mooc_status}")
        print(f"  [2] NEU选位监控    {seat_status}")
        print(f"  [3] 全部运行")
        print(f"  [4] 配置管理")
        print(f"  [0] 退出")
        print("-" * 45)

        choice = input("  请选择: ").strip()

        if choice == "1":
            if not mooc_ready:
                print("\n  ⚠ MOOC检测未配置完整，请先运行 [4]配置管理")
                continue
            return "mooc"
        elif choice == "2":
            if not seat_ready:
                print("\n  ⚠ 选位监控未配置完整，请先运行 [4]配置管理")
                continue
            return "seat"
        elif choice == "3":
            if not mooc_ready and not seat_ready:
                print("\n  ⚠ 两个功能都未配置，请先运行 [4]配置管理")
                continue
            return "all"
        elif choice == "4":
            config_menu(settings)
            # 刷新状态
            mooc_ready = check_feature_ready("mooc")
            seat_ready = check_feature_ready("seat")
        elif choice == "0":
            return "quit"
        else:
            print("  无效选择，请重新输入")

def config_menu(settings):
    """配置管理子菜单"""
    while True:
        mooc_on = settings.get("mooc", True)
        seat_on = settings.get("seat", True)
        mooc_ready = check_feature_ready("mooc")
        seat_ready = check_feature_ready("seat")

        print("\n" + "-" * 45)
        print("  配置管理")
        print("-" * 45)
        print(f"  [1] MOOC检测: {'启用' if mooc_on else '暂停'} {'✅' if mooc_ready else '⚠未配置'}")
        print(f"  [2] 选位监控: {'启用' if seat_on else '暂停'} {'✅' if seat_ready else '⚠未配置'}")
        print(f"  [3] 编辑配置文件")
        print(f"  [0] 返回")
        print("-" * 45)

        choice = input("  请选择: ").strip()

        if choice == "1":
            settings["mooc"] = not mooc_on
            save_settings(settings)
            print(f"  MOOC检测 → {'启用' if settings['mooc'] else '暂停'}")
        elif choice == "2":
            settings["seat"] = not seat_on
            save_settings(settings)
            print(f"  选位监控 → {'启用' if settings['seat'] else '暂停'}")
        elif choice == "3":
            edit_config_files()
        elif choice == "0":
            return
        else:
            print("  无效选择")

def edit_config_files():
    """列出所有配置文件供用户编辑"""
    config_dir = HERE / "config"
    files = sorted(config_dir.glob("*"))
    files = [f for f in files if f.is_file() and f.name != "settings"]

    print("\n  配置文件列表:")
    for i, f in enumerate(files, 1):
        has = _has_content(f)
        status = "✅" if has else "⏹ 空"
        print(f"  [{i}] {f.name:<20} {status}")
    print(f"  [0] 返回")

    choice = input("  输入编号编辑(用系统记事本打开): ").strip()
    if choice == "0" or not choice.isdigit():
        return
    idx = int(choice) - 1
    if 0 <= idx < len(files):
        subprocess.Popen(["notepad", str(files[idx])])
        print(f"  已打开 {files[idx].name}，编辑后保存即可")

# ========== 启动功能 ==========
def run_mooc():
    """运行MOOC检测"""
    print("\n▶ 启动 MOOC 作业检测...\n")
    try:
        subprocess.run([sys.executable, str(HERE / "webtask.py")])
    except KeyboardInterrupt:
        pass

def run_seat():
    """运行选位监控"""
    print("\n▶ 启动 NEU 选位监控...\n")
    print("  (Ctrl+C 可随时停止)")
    try:
        subprocess.run([sys.executable, str(HERE / "seathehero.py")])
    except KeyboardInterrupt:
        pass

# ========== 入口 ==========
def main():
    # 首次运行 → 强制设置
    missing = check_first_run()
    if missing:
        setup_wizard()
        input("\n设置完成后按回车进入主菜单...")

    settings = load_settings()

    while True:
        action = show_menu(settings)
        if action == "quit":
            print("\n  再见！")
            break
        elif action == "mooc":
            run_mooc()
        elif action == "seat":
            run_seat()
        elif action == "all":
            mooc_ready = check_feature_ready("mooc")
            seat_ready = check_feature_ready("seat")
            if mooc_ready and settings.get("mooc", True):
                run_mooc()
            if seat_ready and settings.get("seat", True):
                run_seat()

if __name__ == "__main__":
    main()
