from n64recomp_kit.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["local-llm-doctor"] + __import__("sys").argv[1:]))
