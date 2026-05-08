from flask import Flask, render_template, request, redirect, url_for
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError
from datetime import datetime, timezone
import os, time, uuid

app = Flask(__name__)
app.secret_key = "docker-quiz-secret-2024-xyz"

# ── MongoDB ─────────────────────────────────────────────────────────────────
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")

def get_db():
    for i in range(5):
        try:
            c = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
            c.admin.command("ping")
            print(f"✅ MongoDB connected")
            return c["dockerquiz"]
        except ServerSelectionTimeoutError:
            print(f"⏳ MongoDB not ready ({i+1}/5)...")
            time.sleep(2)
    print("⚠️  Running without MongoDB")
    return MongoClient(MONGO_URI, serverSelectionTimeoutMS=500)["dockerquiz"]

db           = get_db()
profiles_col = db["profiles"]
results_col  = db["results"]
states_col   = db["quiz_states"]

# ── Questions ───────────────────────────────────────────────────────────────
QUESTIONS = [
    {"id":1,"question":"What is Docker primarily used for?","options":["A. Virtual machine management","B. Containerizing applications for consistent environments","C. Cloud storage solutions","D. Database management"],"answer":"B","explanation":"Docker packages applications and their dependencies into lightweight containers that run consistently across different environments.","points":10},
    {"id":2,"question":"Which command initializes Docker configuration files in your project?","options":["A. docker run","B. docker build","C. docker init","D. docker compose up"],"answer":"C","explanation":"`docker init` creates a Dockerfile, .dockerignore, and docker-compose.yml automatically for your project.","points":10},
    {"id":3,"question":"What is a Dockerfile?","options":["A. A log file for Docker errors","B. A script of instructions to build a Docker image","C. A configuration file for Docker Desktop","D. A file that lists running containers"],"answer":"B","explanation":"A Dockerfile is a text file with step-by-step instructions Docker uses to build an image.","points":10},
    {"id":4,"question":"What is the difference between a Docker Image and a Docker Container?","options":["A. They are the same thing","B. An image is a running instance; a container is a blueprint","C. An image is a blueprint; a container is a running instance","D. Images are for Windows, containers are for Linux"],"answer":"C","explanation":"An image is the read-only blueprint (like a class). A container is a live, running instance of that image (like an object).","points":10},
    {"id":5,"question":"Which command builds a Docker image from a Dockerfile?","options":["A. docker run .","B. docker build -t myapp .","C. docker start myapp","D. docker pull myapp"],"answer":"B","explanation":"`docker build -t myapp .` builds an image tagged myapp using the Dockerfile in the current directory.","points":10},
    {"id":6,"question":"What does the -p 8080:80 flag do in docker run -p 8080:80 myapp?","options":["A. Runs the container on port 80 only","B. Maps host port 8080 to container port 80","C. Limits CPU to 80% with 8080 threads","D. Creates a network called 8080:80"],"answer":"B","explanation":"Port mapping format is HOST:CONTAINER. -p 8080:80 lets you access the container port 80 via port 8080 on your machine.","points":10},
    {"id":7,"question":"What is Docker Compose used for?","options":["A. Writing Dockerfiles faster","B. Managing multi-container applications with a single YAML file","C. Monitoring Docker containers","D. Pushing images to Docker Hub"],"answer":"B","explanation":"Docker Compose lets you define and run multi-container apps with one docker-compose.yml file.","points":10},
    {"id":8,"question":"What is Docker Hub?","options":["A. The Docker CLI tool","B. A local registry on your machine","C. A cloud-based registry for storing and sharing Docker images","D. Docker's monitoring dashboard"],"answer":"C","explanation":"Docker Hub is like GitHub but for Docker images — a public registry where you can push, pull, and share container images.","points":10},
    {"id":9,"question":"Which Dockerfile instruction sets the base image?","options":["A. BASE","B. START","C. FROM","D. ORIGIN"],"answer":"C","explanation":"FROM is always the first instruction in a Dockerfile. E.g., FROM python:3.11-slim.","points":10},
    {"id":10,"question":"What does .dockerignore do?","options":["A. Stops Docker from running certain containers","B. Lists files/folders to exclude from the Docker build context","C. Ignores Docker errors during build","D. Disables Docker networking"],"answer":"B","explanation":"Like .gitignore, .dockerignore prevents unnecessary files from being sent to the Docker daemon during builds.","points":10},
    {"id":11,"question":"Which command lists all currently running Docker containers?","options":["A. docker list","B. docker show","C. docker ps","D. docker containers"],"answer":"C","explanation":"docker ps shows running containers. Add -a to see ALL containers including stopped ones.","points":10},
    {"id":12,"question":"What does the EXPOSE instruction in a Dockerfile do?","options":["A. Automatically publishes the port to the host","B. Documents which port the container listens on","C. Opens a firewall rule","D. Exposes environment variables"],"answer":"B","explanation":"EXPOSE is documentation — it tells developers which port the app uses, but you still need -p in docker run to publish it.","points":10},
    {"id":13,"question":"What is a Docker Volume used for?","options":["A. Increasing container CPU usage","B. Persisting data beyond a container's lifecycle","C. Connecting containers to the internet","D. Reducing image size"],"answer":"B","explanation":"Volumes persist data on the host so it survives container restarts and removals.","points":10},
    {"id":14,"question":"What command stops a running container named webserver?","options":["A. docker kill webserver","B. docker pause webserver","C. docker stop webserver","D. docker end webserver"],"answer":"C","explanation":"docker stop webserver gracefully stops the container by sending SIGTERM.","points":10},
    {"id":15,"question":"What does docker pull python:3.11-slim do?","options":["A. Creates a Python container","B. Downloads the python:3.11-slim image from Docker Hub","C. Installs Python 3.11 on your machine","D. Updates an existing Python container"],"answer":"B","explanation":"docker pull downloads an image from a registry to your local machine without running it.","points":10},
    {"id":16,"question":"In a docker-compose.yml, what does depends_on specify?","options":["A. The Docker version required","B. Service startup order dependencies","C. Required system packages","D. Network port dependencies"],"answer":"B","explanation":"depends_on ensures one service starts before another.","points":10},
    {"id":17,"question":"What is a multi-stage Docker build used for?","options":["A. Running multiple containers simultaneously","B. Building images for multiple OS platforms","C. Reducing final image size by separating build and runtime stages","D. Creating multiple versions of the same app"],"answer":"C","explanation":"Multi-stage builds separate compile and runtime stages — only artifacts are copied to a slim final image.","points":10},
    {"id":18,"question":"Which command removes all stopped containers and unused images?","options":["A. docker clean all","B. docker system prune","C. docker remove --all","D. docker flush"],"answer":"B","explanation":"docker system prune frees disk space by removing stopped containers, unused networks, and dangling images.","points":10},
    {"id":19,"question":"What does the CMD instruction in a Dockerfile define?","options":["A. The command to run when building the image","B. A required command that cannot be overridden","C. The default command to run when a container starts","D. A comment/description for the Dockerfile"],"answer":"C","explanation":"CMD sets the default command when a container starts. Unlike ENTRYPOINT, it can be overridden in docker run.","points":10},
    {"id":20,"question":"What is the purpose of Docker networking?","options":["A. To connect Docker to Wi-Fi","B. To allow containers to communicate with each other and the outside world","C. To monitor network traffic on the host","D. To share files between containers"],"answer":"B","explanation":"Docker networks enable containers to talk to each other and to external services.","points":10},
]

TOTAL_POINTS = sum(q["points"] for q in QUESTIONS)

def get_grade(score, total):
    pct = (score / total) * 100
    if pct >= 90:   return "Docker Captain",    "🏆", "#00d4aa"
    elif pct >= 75: return "Container Expert",  "🥇", "#3b9eff"
    elif pct >= 60: return "Image Builder",     "🥈", "#f5a623"
    elif pct >= 40: return "Dockerfile Rookie", "🥉", "#e76f51"
    else:           return "Whale Watcher",     "🐋", "#9b5de5"

def load_state(sid):
    try:
        return states_col.find_one({"sid": sid})
    except Exception:
        return None

def save_state(sid, data):
    try:
        data["sid"] = sid
        states_col.replace_one({"sid": sid}, data, upsert=True)
    except Exception as e:
        print(f"⚠️  save_state failed: {e}")

# ── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/start")
def start():
    return redirect(url_for("index"))

@app.route("/create-profile", methods=["POST"])
def create_profile():
    name   = request.form.get("name", "").strip()
    avatar = request.form.get("avatar", "🐋")
    role   = request.form.get("role", "Student")

    if not name:
        return redirect(url_for("index"))

    # Unique ID lives in the URL — zero cookie/session dependency
    sid = uuid.uuid4().hex

    profile_id = "no-db"
    try:
        r = profiles_col.insert_one({
            "name": name, "avatar": avatar, "role": role,
            "created_at": datetime.now(timezone.utc),
        })
        profile_id = str(r.inserted_id)
    except Exception as e:
        print(f"⚠️  profile insert: {e}")

    save_state(sid, {
        "profile_id":     profile_id,
        "profile_name":   name,
        "profile_avatar": avatar,
        "score":          0,
        "current":        0,
        "wrong":          [],
    })

    return redirect(url_for("question", sid=sid))


@app.route("/question/<sid>")
def question(sid):
    state = load_state(sid)
    if not state:
        return redirect(url_for("index"))

    idx = state.get("current", 0)
    if idx >= len(QUESTIONS):
        return redirect(url_for("results", sid=sid))

    return render_template("question.html",
        sid=sid,
        question=QUESTIONS[idx],
        current=idx + 1,
        total=len(QUESTIONS),
        score=state["score"],
        profile_name=state["profile_name"],
        profile_avatar=state["profile_avatar"],
    )


@app.route("/answer/<sid>", methods=["POST"])
def answer(sid):
    state = load_state(sid)
    if not state:
        return redirect(url_for("index"))

    idx = state.get("current", 0)
    if idx >= len(QUESTIONS):
        return redirect(url_for("results", sid=sid))

    q          = QUESTIONS[idx]
    selected   = request.form.get("choice", "")
    is_correct = selected == q["answer"]

    score = state["score"]
    wrong = list(state.get("wrong", []))

    if is_correct:
        score += q["points"]
    else:
        wrong.append(idx)

    new_idx = idx + 1
    state.update({"score": score, "current": new_idx, "wrong": wrong})
    save_state(sid, state)

    return render_template("feedback.html",
        sid=sid,
        question=q,
        selected=selected,
        is_correct=is_correct,
        current=new_idx,
        total=len(QUESTIONS),
        score=score,
        profile_name=state["profile_name"],
        profile_avatar=state["profile_avatar"],
    )


@app.route("/results/<sid>")
def results(sid):
    state = load_state(sid)
    if not state:
        return redirect(url_for("index"))

    score     = state["score"]
    wrong_ids = state.get("wrong", [])
    wrong_qs  = [QUESTIONS[i] for i in wrong_ids]
    grade_name, grade_emoji, grade_color = get_grade(score, TOTAL_POINTS)
    pct = round((score / TOTAL_POINTS) * 100)

    try:
        results_col.insert_one({
            "profile_id":         state.get("profile_id"),
            "name":               state["profile_name"],
            "avatar":             state["profile_avatar"],
            "score":              score,
            "total":              TOTAL_POINTS,
            "percentage":         pct,
            "grade":              grade_name,
            "num_correct":        len(QUESTIONS) - len(wrong_ids),
            "num_wrong":          len(wrong_ids),
            "wrong_question_ids": [QUESTIONS[i]["id"] for i in wrong_ids],
            "completed_at":       datetime.now(timezone.utc),
        })
        states_col.delete_one({"sid": sid})
    except Exception as e:
        print(f"⚠️  results save: {e}")

    return render_template("results.html",
        score=score, total=TOTAL_POINTS, pct=pct,
        grade_name=grade_name, grade_emoji=grade_emoji, grade_color=grade_color,
        wrong_qs=wrong_qs,
        num_correct=len(QUESTIONS) - len(wrong_ids),
        total_questions=len(QUESTIONS),
        profile_name=state["profile_name"],
        profile_avatar=state["profile_avatar"],
    )


@app.errorhandler(404)
def not_found(e):
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)