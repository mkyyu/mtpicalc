# main.py
import subprocess, sys, importlib, time, math, platform
import sys
sys.set_int_max_str_digits(100000000000000000000000000000000000000)

from multiprocessing import Process, Queue, cpu_count

# Auto-install any missing packages
def ensure_package(package, import_as=None):
    import_as = import_as or package
    try:
        return importlib.import_module(import_as)
    except ImportError:
        print(f"[INFO] Installing '{package}'...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        return importlib.import_module(import_as)

# Required packages
flask = ensure_package("flask")
tqdm = ensure_package("tqdm")

# Optional gmpy2
try:
    gmpy2 = ensure_package("gmpy2")
    _ = gmpy2.mpfr("3.14")
    gmpy2_available = True
    mpf = gmpy2.mpfr
except Exception:
    gmpy2 = None
    gmpy2_available = False
    import decimal
    decimal.getcontext().prec = 110
    mpf = decimal.Decimal
    print("[WARNING] gmpy2 is not usable; using 'decimal' fallback.")

def setup_precision(digits, use_gmpy2):
    if use_gmpy2 and gmpy2_available:
        gmpy2.get_context().precision = digits + 10
    else:
        import decimal
        decimal.getcontext().prec = digits + 10

def chudnovsky_term(k, use_gmpy2):
    k = int(k)
    num = math.factorial(6 * k) * (545140134 * k + 13591409)
    denom = math.factorial(3 * k) * math.factorial(k)**3 * (-262537412640768000)**k
    if use_gmpy2 and gmpy2_available:
        return mpf(str(num)) / mpf(str(denom))
    else:
        import decimal
        return decimal.Decimal(num) / decimal.Decimal(denom)

def compute_terms(start_k, end_k, q, pid, use_gmpy2):
    setup_precision(0, use_gmpy2)
    partial_sum = mpf(0)
    t_start = time.time()
    for k in range(start_k, end_k):
        partial_sum += chudnovsky_term(k, use_gmpy2)
    t_end = time.time()
    q.put((pid, partial_sum, t_end - t_start))

def compute_pi(digits=1000, num_processes=None, use_gmpy2=True):
    setup_precision(digits, use_gmpy2)

    if use_gmpy2 and gmpy2_available:
        C = mpf(426880) * gmpy2.sqrt(mpf(10005))
    else:
        C = mpf(426880) * mpf(10005).sqrt()

    num_terms = digits // 14 + 1
    if not num_processes:
        num_processes = cpu_count()

    terms_per_process = num_terms // num_processes
    processes, results = [], []
    q = Queue()
    start = time.time()

    for i in range(num_processes):
        start_k = i * terms_per_process
        end_k = num_terms if i == num_processes - 1 else (i + 1) * terms_per_process
        p = Process(target=compute_terms, args=(start_k, end_k, q, i, use_gmpy2))
        processes.append(p)
        p.start()

    for _ in processes:
        results.append(q.get())
    for p in processes:
        p.join()

    results.sort()
    total_sum = sum(r[1] for r in results)
    pi = C / total_sum
    end = time.time()

    return {
        "pi": str(pi)[:digits + 2],
        "digits": digits,
        "time": round(end - start, 4),
        "processes": num_processes,
        "gmpy2": gmpy2_available and use_gmpy2,
        "timings": [{"process": r[0], "seconds": round(r[2], 4)} for r in results]
    }

# --- Web UI ---
app = flask.Flask(__name__)

@app.route("/")
def home():
    return open("index.html").read()

@app.route("/compute", methods=["POST"])
def api_compute():
    data = flask.request.json
    digits = int(data.get("digits", 1000))
    processes = int(data.get("processes", cpu_count()))
    use_gmpy = data.get("use_gmpy2", True)
    result = compute_pi(digits=digits, num_processes=processes, use_gmpy2=use_gmpy)
    return flask.jsonify(result)

if __name__ == "__main__":
    print("Starting π mPiCalc Web v2.1...")
    print(f"Backend: {'gmpy2' if gmpy2_available else 'decimal'} | Python {platform.python_version()} | OS: {platform.system()}")
    import webbrowser
    webbrowser.open("http://127.0.0.1:5000")
    app.run(debug=True)
