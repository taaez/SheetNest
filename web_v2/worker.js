// SheetNest 웹 작업자(Web Worker).
// 브라우저 안에서 Python(Pyodide)을 띄우고 팀 코드(py.zip)를 그대로 실행한다.
// 계산을 화면과 분리해 돌리기 때문에 배치가 몇 초 걸려도 화면이 멈추지 않는다.

const DEFAULT_PYODIDE = "https://cdn.jsdelivr.net/pyodide/v0.28.3/full/";
const UPLOAD_DIR = "/tmp/sheetnest_upload";

let pyodide = null;
let bridge = null;
let drawingReaders = false;

const post = (type, payload = {}) => self.postMessage({ type, ...payload });

async function init(base) {
  const url = base || DEFAULT_PYODIDE;
  post("status", { text: "계산 준비 중입니다. 처음 열 때는 조금 걸립니다." });
  importScripts(url + "pyodide.js");
  pyodide = await loadPyodide({ indexURL: url });
  post("status", { text: "계산 코드를 불러오고 있습니다." });
  const zip = await fetch("py.zip", { cache: "no-cache" });
  if (!zip.ok) throw new Error("계산 코드(py.zip)를 찾지 못했습니다. python tools/build_web.py 로 site/를 만든 뒤 열면 됩니다.");
  pyodide.FS.mkdirTree("/sheetnest");
  pyodide.unpackArchive(await zip.arrayBuffer(), "zip", { extractDir: "/sheetnest" });
  pyodide.FS.mkdirTree(UPLOAD_DIR);
  pyodide.runPython('import sys; sys.path.insert(0, "/sheetnest")');
  bridge = pyodide.pyimport("bridge");
  const methods = JSON.parse(bridge.methods());
  const instances = await (await fetch("data/index.json", { cache: "no-cache" })).json();
  post("ready", { methods, instances });
}

// DXF, SVG 읽기 라이브러리는 필요할 때 한 번만 내려받는다(수 MB).
async function ensureDrawingReaders() {
  if (drawingReaders) return;
  post("status", { text: "도면 읽기 도구를 내려받고 있습니다. 처음 한 번만 내려받습니다." });
  try {
    await pyodide.loadPackage("micropip");
    const micropip = pyodide.pyimport("micropip");
    await micropip.install(["ezdxf", "svgelements"]);
  } catch (e) {
    throw new Error(
      "도면 읽기 도구를 내려받지 못했습니다. PC에서 python tools/convert.py 로 JSON으로 바꾼 뒤 그 파일을 올리면 됩니다."
    );
  }
  drawingReaders = true;
}

async function loadBuiltin(file) {
  const res = await fetch(file);
  if (!res.ok) throw new Error(`${file} 파일을 불러오지 못했습니다`);
  const path = `${UPLOAD_DIR}/${file.split("/").pop()}`;
  pyodide.FS.writeFile(path, new Uint8Array(await res.arrayBuffer()));
  return JSON.parse(bridge.load_path(path));
}

async function loadUpload(name, buffer, options) {
  const ext = name.toLowerCase().split(".").pop();
  if (ext === "dxf" || ext === "svg") await ensureDrawingReaders();
  const safe = name.replace(/[^\w.\-가-힣]/g, "_");
  const path = `${UPLOAD_DIR}/${safe}`;
  pyodide.FS.writeFile(path, new Uint8Array(buffer));
  return JSON.parse(bridge.load_upload_path(path, JSON.stringify(options || {})));
}

self.onmessage = async (ev) => {
  const m = ev.data;
  try {
    if (m.type === "init") {
      await init(m.pyodide);
    } else if (m.type === "loadBuiltin") {
      post("instance", { data: await loadBuiltin(m.file), origin: m.file });
    } else if (m.type === "loadUpload") {
      post("instance", { data: await loadUpload(m.name, m.buffer, m.options), origin: m.name });
    } else if (m.type === "run") {
      for (const name of m.methods) {
        post("running", { method: name });
        const json = bridge.run_method(name, JSON.stringify((m.params || {})[name] || {}));
        post("result", { result: JSON.parse(json) });
      }
      post("done");
    } else if (m.type === "instanceJson") {
      post("instanceJson", { text: bridge.current_instance_json() });
    }
  } catch (e) {
    post("error", { during: m.type, text: cleanError(e) });
  }
};

// Python 예외는 긴 추적 정보가 붙어 오므로 마지막 줄(실제 원인)만 화면에 보낸다.
function cleanError(e) {
  const text = String((e && e.message) || e).trim();
  const lines = text.split("\n").filter((s) => s.trim());
  const last = lines.length > 1 ? lines[lines.length - 1] : text;
  return last.replace(/^([\w.]*(Error|Exception)):\s*/, "");
}
