from n64recomp_kit.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["emit-local-llm-workflow"] + __import__("sys").argv[1:]))
