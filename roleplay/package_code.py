"""Build the teacher's code attachment without test data, predictions or model weights."""
from pathlib import Path
import zipfile


def main():
    root = Path(__file__).resolve().parents[1]
    out = root / "roleplay/report/roleplay_code.zip"
    files = list((root / "roleplay").glob("*.py")) + [root / "README.md", root / "报告模板.docx"]
    files += [root / p for p in ("roleplay/requirements.txt", "roleplay/README.md",
              "roleplay/report/content.md", "roleplay/report/artifact.md", "roleplay/report/Dockerfile")]
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            archive.write(path, path.relative_to(root))
        archive.writestr("README_CODE.txt", "本代码附件不包含测试数据、预测结果或模型权重。\n"
            "请将老师的数据包放入项目根目录的 基于大模型的角色扮演/，安装 roleplay/requirements.txt 后运行离线测试。\n"
            "API 密钥只通过本地环境变量配置，默认拒绝 HTTP。复建报告还需要仓库中已公开的实验结果。\n"
            "运行说明见 roleplay/README.md，电子存档时将附件按本人学号-姓名.zip 重命名。\n")
    if out.stat().st_size > 10 * 1024 * 1024:
        raise SystemExit("Code attachment exceeds 10 MiB")
    with zipfile.ZipFile(out) as archive:
        if any(name.startswith(("基于大模型的角色扮演/", "roleplay/runs/", "roleplay/results/")) for name in archive.namelist()):
            raise SystemExit("Forbidden dataset or prediction included")
    print(out, out.stat().st_size)


if __name__ == "__main__":
    main()
