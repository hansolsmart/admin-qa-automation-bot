import argparse
import sqlite3
from contextlib import closing
from pathlib import Path


def snapshot(source: Path, destination: Path) -> None:
    source = source.resolve(strict=True)
    destination = destination.resolve()
    if source == destination:
        raise ValueError("원본과 대상은 다른 파일이어야 합니다.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.touch(exist_ok=False)
    try:
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as original:
            with closing(sqlite3.connect(destination)) as copy:
                original.backup(copy)
                if copy.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                    raise ValueError("SQLite 무결성 검사 실패")
                if copy.execute("PRAGMA foreign_key_check").fetchone() is not None:
                    raise ValueError("SQLite 참조 무결성 검사 실패")
    except Exception:
        destination.unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser(description="SQLite를 새 경로로 복사하고 무결성을 검사합니다.")
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    try:
        snapshot(args.source, args.destination)
    except (OSError, sqlite3.Error, ValueError) as error:
        parser.error(str(error))
    print("SQLite 스냅샷 저장 및 integrity_check·foreign_key_check 통과")


if __name__ == "__main__":
    main()
