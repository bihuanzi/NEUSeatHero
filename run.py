"""
总控台 - 统一管理 MOOC检测 和 NEU选位监控
  python run.py          → 自动模式（按已保存配置静默运行）
  python run.py --config → 交互模式（菜单配置）
首次运行自动进入设置向导
"""
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).parent

# ========== 配置检查 ==========
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

# ========== 设置 ==========
def load_settings():
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
    path = HERE / "config" / "settings"
    lines = ["# 功能开关 true=启用 false=禁用"]
    for k, v in settings.items():
        lines.append(f"{k}={'true' if v else 'false'}")
    path.write_text("\n".join(lines), encoding='utf-8')

def is_first_run():
    """没有 settings 文件 = 首次运行"""
    return not (HERE / "config" / "settings").exists()

# ========== 设置向导 ==========
def setup_wizard():
    """首次运行：自动配置 + 选择功能"""
    print("\n" + "=" * 50)
    print("  pram_lifecontroler 首次设置")
    print("=" * 50)

    # 检查必要配置
    need_notify = not _has_content(HERE / "config" / "notify")
    need_mooc = not _has_content(HERE / "config" / "aimLesson")
    need_seat = not _has_content(HERE / "config" / "mathe_auth")

    if need_notify or need_mooc or need_seat:
        print("\n  需要配置以下文件（可在config/目录找到.example模板）：\n")
        if need_notify:
            print("  ⚠ config/notify - SMTP邮件通知")
        if need_mooc:
            print("  ⚠ config/aimLesson - MOOC课程URL")
        if need_seat:
            print("  ⚠ config/mathe_auth - 选位系统账号密码")

        print("\n  请在VS Code中编辑上述文件，完成后按回车...")
        input()

    # 选择启用功能
    print("\n  选择要启用的功能：")
    print("  [1] 仅MOOC作业检测")
    print("  [2] 仅NEU选位监控")
    print("  [3] 全部启用")
    print("  [0] 都不启用（仅保存配置）")

    choice = input("  请选择: ").strip()
    settings = {}
    if choice == "1":
        settings = {"mooc": True, "seat": False}
    elif choice == "2":
        settings = {"mooc": False, "seat": True}
    elif choice == "3":
        settings = {"mooc": True, "seat": True}
    else:
        settings = {"mooc": False, "seat": False}

    save_settings(settings)
    print(f"\n  ✅ 设置完成！MOOC={'开' if settings['mooc'] else '关'} | 选位={'开' if settings['seat'] else '关'}")
    print(f"  下次运行 python run.py 将自动执行")
    print(f"  要更改配置请运行 python run.py --config\n")
    return settings

# ========== 交互菜单（--config 模式） ==========
def interactive_menu(settings):
    """主动唤起的交互菜单"""
    while True:
        mooc_ready = check_feature_ready("mooc")
        seat_ready = check_feature_ready("seat")
        mooc_on = settings.get("mooc", True)
        seat_on = settings.get("seat", True)

        print("\n" + "=" * 45)
        print("  pram_lifecontroler 配置面板")
        print("=" * 45)
        mooc_s = "✅" if (mooc_on and mooc_ready) else ("⚠未配置" if mooc_on else "⏸ 暂停")
        seat_s = "✅" if (seat_on and seat_ready) else ("⚠未配置" if seat_on else "⏸ 暂停")
        print(f"  [1] MOOC作业检测   {mooc_s}")
        print(f"  [2] NEU选位监控    {seat_s}")
        print(f"  [3] 立即手动运行")
        print(f"  [4] 开关功能 / 编辑配置")
        print(f"  [0] 退出")
        print("-" * 45)

        choice = input("  请选择: ").strip()

        if choice == "1":
            toggle_feature(settings, "mooc")
        elif choice == "2":
            toggle_feature(settings, "seat")
        elif choice == "3":
            if mooc_ready and mooc_on:
                run_mooc()
            if seat_ready and seat_on:
                run_seat()
        elif choice == "4":
            config_submenu(settings)
            mooc_ready = check_feature_ready("mooc")
            seat_ready = check_feature_ready("seat")
        elif choice == "0":
            return
        else:
            print("  无效选择")

def toggle_feature(settings, name):
    settings[name] = not settings.get(name, True)
    save_settings(settings)
    label = "MOOC检测" if name == "mooc" else "选位监控"
    print(f"  {label} → {'启用' if settings[name] else '暂停'}")

def config_submenu(settings):
    while True:
        mooc_on = settings.get("mooc", True)
        seat_on = settings.get("seat", True)

        print("\n" + "-" * 40)
        print("  [1] MOOC检测: " + ("启用" if mooc_on else "暂停"))
        print("  [2] 选位监控: " + ("启用" if seat_on else "暂停"))
        print("  [3] 编辑配置文件")
        print("  [0] 返回")

        choice = input("  > ").strip()
        if choice == "1":
            toggle_feature(settings, "mooc")
        elif choice == "2":
            toggle_feature(settings, "seat")
        elif choice == "3":
            edit_config_files()
        elif choice == "0":
            return

def edit_config_files():
    config_dir = HERE / "config"
    files = sorted([f for f in config_dir.glob("*") if f.is_file() and f.name != "settings"])
    print("\n  配置文件:")
    for i, f in enumerate(files, 1):
        print(f"  [{i}] {f.name:<20} {'✅' if _has_content(f) else '⏹ 空'}")
    print(f"  [0] 返回")
    choice = input("  输入编号打开: ").strip()
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(files):
            subprocess.Popen(["notepad", str(files[idx])])

# ========== 启动功能 ==========
def run_mooc():
    print("\n▶ MOOC作业检测...")
    try:
        subprocess.run([sys.executable, str(HERE / "webtask.py")])
    except KeyboardInterrupt:
        pass

def run_seat():
    print("\n▶ NEU选位监控... (Ctrl+C停止)")
    try:
        subprocess.run([sys.executable, str(HERE / "seathehero.py")])
    except KeyboardInterrupt:
        pass

# ========== 自动模式（计划任务触发） ==========
def auto_run(settings):
    """无交互自动执行已启用的功能"""
    mooc_on = settings.get("mooc", False)
    seat_on = settings.get("seat", False)

    if mooc_on and check_feature_ready("mooc"):
        run_mooc()
    if seat_on and check_feature_ready("seat"):
        run_seat()

    if not mooc_on and not seat_on:
        print("  未启用任何功能，运行 python run.py --config 配置")

# ========== 入口 ==========
def main():
    # --config 模式 → 强制交互菜单
    if "--config" in sys.argv or "-c" in sys.argv:
        settings = load_settings()
        if not settings:
            settings = setup_wizard()
        interactive_menu(settings)
        return

    # 首次运行 → 设置向导 → 然后自动执行
    if is_first_run():
        settings = setup_wizard()
    else:
        settings = load_settings()

    # 自动模式
    auto_run(settings)

if __name__ == "__main__":
    main()
