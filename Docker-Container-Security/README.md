# Docker Container Security -- A Hands-On Self-Study Guide

![Difficulty](https://img.shields.io/badge/Difficulty-Beginner%20Friendly-4CAF50?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-blue?style=flat-square)
![Docker](https://img.shields.io/badge/Docker-Required-2496ED?style=flat-square&logo=docker&logoColor=white)

This guide walks you through Docker container security from first principles. Every concept is explained before you use it. Every command is broken down flag by flag. You will not just run commands -- you will understand exactly what each one does and why it matters.

By the end of this guide you will have built five progressively more secure versions of the same application and will understand the reasoning behind every decision.

---

## Prerequisites

You need Docker installed on Ubuntu or Debian. To check:

```bash
docker --version
```

If Docker is not installed:

```bash
sudo apt update
sudo apt install -y docker.io
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER
```

After running `usermod`, log out and log back in. Then confirm Docker works:

```bash
docker run hello-world
```

You should see a message confirming Docker is working correctly.

---

## How This Guide Is Structured

The guide is organised into five scenarios. Each scenario builds on the previous one. Within each scenario, you follow numbered steps.

```
Scenario 1  The Insecure Default
Scenario 2  Running as a Non-Root User
Scenario 3  Protecting Secrets with .dockerignore
Scenario 4  Multi-Stage Builds
Scenario 5  Runtime Hardening
```

Each scenario has:
- An objective explaining what you will learn
- A command reference table before any commands are run
- Numbered steps to follow
- A checkpoint to confirm the concept landed
- A summary of what was covered
- Reflection questions before moving on

---

## Core Concepts Before You Begin

Before touching any command, read this section. These are the building blocks everything else rests on.

### What is Docker?

Docker packages your application and everything it needs to run -- code, runtime, libraries, configuration -- into a single portable unit called a container. The same container runs identically on your laptop, a colleague's machine, or a production server.

### Images and Containers

| Term | What it means |
|---|---|
| Image | A read-only blueprint stored on disk. Think of it as a recipe. |
| Container | A running instance created from an image. Think of it as the meal. |
| Dockerfile | A plain text file with instructions for building an image. |

You build an image once. You can run many containers from it. A Dockerfile is the script Docker follows to create the image.

### What is a Layer?

Every instruction in a Dockerfile creates a layer. Layers stack on top of each other to form the final image. Docker stores each layer separately, which enables caching.

```
Layer 5  CMD ["node", "app.js"]       <- top
Layer 4  COPY app.js .
Layer 3  RUN npm install
Layer 2  WORKDIR /app
Layer 1  FROM node:20-slim            <- bottom (base image)
```

### Layer Caching -- Why Order Matters

When you rebuild an image, Docker checks each layer from bottom to top. If a layer has not changed since the last build, Docker reuses it from cache instead of running it again. This is called a cache hit.

If a layer changes, Docker rebuilds that layer and every layer above it. This is called cache invalidation.

This means the order of instructions in your Dockerfile directly affects build speed. Instructions that change frequently -- like copying your source code -- should go near the bottom. Instructions that change rarely -- like installing dependencies -- should go near the top.

```
# Slow and inefficient: any code change forces npm install to re-run every time
COPY . .
RUN npm install

# Fast and correct: npm install only re-runs when package.json changes
COPY package.json ./
RUN npm install
COPY . .
```

You will observe this difference directly using the `time` command in Scenario 1.

---

## Repository Structure

Create the following folder. All files in this guide go inside it.

```
docker-labs/
|-- app.js
|-- package.json
|-- .env
|-- .dockerignore          (created in Scenario 3)
|-- Dockerfile             (Scenario 1)
|-- Dockerfile.nonroot     (Scenario 2)
|-- Dockerfile.multistage  (Scenario 4)
```

```bash
mkdir docker-labs
cd docker-labs
```

---

## The Sample Application

The application is intentionally minimal. Its only job is to print the user ID running inside the container. This makes the difference between root and non-root immediately visible in the terminal output.

**Create `app.js`**

Open your preferred text editor, create a file named `app.js` inside `docker-labs/`, and paste the following content exactly:

```javascript
// Import the built-in http module to create a web server
const http = require('http');

// Import the built-in os module to get the container hostname
const os = require('os');

const PORT = 3000;

// process.getuid() returns the numeric user ID of the process running this app.
// Inside a Docker container, if no USER is set in the Dockerfile,
// this will be 0, which means root.
const uid = process.getuid();
const username = uid === 0 ? 'root -- DANGER' : `non-root (uid: ${uid})`;

const server = http.createServer((req, res) => {
  res.writeHead(200, { 'Content-Type': 'text/plain' });
  res.end(
    `App is running\n` +
    `User ID : ${uid}\n` +
    `Running as : ${username}\n` +
    `Hostname : ${os.hostname()}\n`
  );
});

server.listen(PORT, () => {
  console.log(`Server started on port ${PORT}`);
  console.log(`User ID inside container : ${uid}`);
  console.log(`Running as : ${username}`);
});
```

**Create `package.json`**

Create a file named `package.json` inside `docker-labs/` and paste the following:

```json
{
  "name": "docker-security-demo",
  "version": "1.0.0",
  "description": "Minimal app to demonstrate Docker security concepts",
  "main": "app.js",
  "scripts": {
    "start": "node app.js"
  }
}
```

**Create `.env`**

This file simulates a real secrets file. In almost every production project a file like this exists, containing database passwords, API keys, and credentials that the application needs at runtime. Create a file named `.env` and paste the following:

```
DATABASE_PASSWORD=super_secret_password_123
API_KEY=sk-live-abc123xyz789
STRIPE_SECRET=rk_live_do_not_share_this
```

You will see exactly what happens when this file gets accidentally bundled into a Docker image in Scenario 1.

---

## Resetting Between Scenarios

Docker aggressively caches layers. If you move from one scenario to the next without clearing the cache, Docker may reuse layers from a previous build and give you misleading results.

Run the following command before starting each new scenario:

```bash
docker system prune -af
```

| Flag | Meaning |
|---|---|
| `system prune` | Removes all unused Docker objects: stopped containers, unused images, unused networks, and the entire build cache |
| `-a` | Removes all unused images, not just dangling ones. Without this flag, images that are no longer tagged but still referenced by a layer would be kept. |
| `-f` | Force. Skips the confirmation prompt so the command runs immediately. |

Confirm the environment is clean after running this:

```bash
docker images
docker ps -a
```

Both should return empty or minimal output before you proceed.

---

---

# Scenario 1 -- The Insecure Default

## Objective

Understand what a basic Dockerfile looks like, why it is insecure by default, and how Docker layer caching works in practice using timed builds.

## What You Will Learn

- The purpose of each Dockerfile instruction
- Why running a container as root is dangerous
- How Docker layer caching works and how to observe it
- How to detect accidental secret leaks inside an image

---

## Command Reference

| Command or Flag | What it does |
|---|---|
| `docker build` | Builds a Docker image from a Dockerfile |
| `-f Dockerfile` | Specifies which Dockerfile to use. Without `-f`, Docker looks for a file literally named `Dockerfile` in the current directory. Use `-f` when your file has any other name, such as `Dockerfile.nonroot`. |
| `-t insecure-app` | Tags the resulting image with a human-readable name. Without a tag, Docker assigns a random ID that is difficult to reference in later commands. |
| `.` at the end | The build context. This tells Docker which directory to use as the source for `COPY` instructions. The dot means the current directory. |
| `docker run` | Creates and starts a container from an image |
| `-p 3000:3000` | Maps port 3000 on your machine to port 3000 inside the container. The format is `host_port:container_port`. Without this, the app runs but is unreachable from your terminal or browser. |
| `docker exec` | Runs a command inside an already-running container |
| `-it` | Two flags combined. `-i` keeps the input stream open so you can type. `-t` allocates a terminal. Together they give you an interactive shell session inside the container. |
| `docker stop` | Gracefully stops a running container |
| `docker ps -q` | Lists only the IDs of currently running containers. Used to pass those IDs into other commands without having to copy them manually. |
| `time` | A shell built-in that wraps any command and reports how long it took to complete. |

---

## Step 1 -- Create the Dockerfile

Create a file named `Dockerfile` inside `docker-labs/` and paste the following content exactly:

```dockerfile
# Use the official Node.js version 20 image as the base.
# This pulls a full Debian-based image (roughly 1 GB) that includes
# compilers, curl, git, apt, and hundreds of other tools.
# Those tools are useful for building software but dangerous
# to leave in a production image.
FROM node:20

# Set the working directory inside the container.
# All subsequent instructions run relative to this path.
# If the directory does not exist, Docker creates it automatically.
WORKDIR /app

# Copy everything from the current directory on your machine
# into /app inside the container.
# This includes app.js and package.json -- but also .env,
# any private keys, and everything else in the folder.
COPY . .

# Install Node.js dependencies inside the container.
# Because no USER instruction has appeared yet,
# this runs as root (uid 0).
RUN npm install

# Document that the container listens on port 3000.
# This is metadata only. It does not publish the port.
# You still need -p when running the container.
EXPOSE 3000

# The command that starts when the container runs.
# No USER was set above, so this process runs as root.
CMD ["npm", "start"]
```

---

## Step 2 -- Observe Layer Caching with Timed Builds

Before building, pull the base image so the download time does not distort your timing measurements:

```bash
docker pull node:20
```

**First build -- nothing is cached yet:**

```bash
time docker build -f Dockerfile -t insecure-app .
```

Watch the output as each layer executes in sequence. Note the time printed at the end under `real`. A typical first build takes 30 to 90 seconds depending on your connection speed.

**Second build -- nothing has changed:**

```bash
time docker build -f Dockerfile -t insecure-app .
```

Every layer should now show `CACHED`. The build completes in under 2 seconds. Docker did not re-execute anything -- it reused every layer from the first build unchanged.

**Third build -- simulate a code change:**

Open `app.js` in your editor and add the following line at the very top of the file:

```javascript
// version 2
```

Save the file. Now rebuild:

```bash
time docker build -f Dockerfile -t insecure-app .
```

Observe which layers show `CACHED` and which do not. The `COPY . .` layer is invalidated because `app.js` changed. Every layer above it -- `RUN npm install` and `CMD` -- also re-executes even though your dependencies did not change. This is the caching problem that a correct `COPY` order would solve.

---

## Step 3 -- Run the Container

```bash
docker run -p 3000:3000 insecure-app
```

Open a second terminal window and send a request to the running container:

```bash
curl http://localhost:3000
```

Expected output:

```
App is running
User ID : 0
Running as : root -- DANGER
Hostname : a3f2b1c9d4e5
```

User ID 0 is root. The application and everything it can reach inside the container is operating with full, unrestricted privileges.

---

## Step 4 -- Confirm the Secret Leak

With the container still running, go to your second terminal and open a shell inside the container:

```bash
docker exec -it $(docker ps -q) sh
```

You are now inside a running shell inside the container. Run:

```bash
cat /app/.env
```

Expected output:

```
DATABASE_PASSWORD=super_secret_password_123
API_KEY=sk-live-abc123xyz789
STRIPE_SECRET=rk_live_do_not_share_this
```

Your credentials are baked into the image. Anyone who can pull this image from a registry can read them with the same command. The image does not need to be running for this -- `docker run --rm insecure-app cat /app/.env` would return the same result.

Exit the shell and stop the container:

```bash
exit
docker stop $(docker ps -q)
```

---

## Summary -- Scenario 1

You built a working Docker image and observed three distinct problems directly.

The application runs as root. User ID 0 has unrestricted access inside the container. If an attacker exploits any vulnerability in the application, they inherit that full access immediately.

The `.env` file is inside the image. `COPY . .` copied everything in the project directory without discrimination, including the secrets file. It is now permanently baked into the image layer and readable without any authentication.

The Dockerfile copies all files before installing dependencies. This means any change to `app.js` -- even a single comment -- invalidates the `npm install` cache layer and forces a full reinstall on every subsequent build.

Layer caching is real and measurable. You observed the difference between a cold build and a fully cached build using the `time` command. Understanding this determines how efficiently your team can build and ship software.

---

## Checkpoint

Before moving to Scenario 2, confirm you observed the following:

1. Run `docker exec -it $(docker ps -q) whoami` against the running container. What name is printed? What does that mean in terms of what the process is permitted to do?
2. Look at your first and second build outputs. How many seconds did each take? How many layers showed `CACHED` on the second run?
3. In the third build after editing `app.js`, which was the first layer that was NOT pulled from cache? What was the layer immediately below it that WAS cached?

---

## Reflection

- If this image contained real AWS access keys in `.env` and you pushed it to a public Docker Hub repository, what could happen and within what timeframe?
- The `RUN npm install` layer re-ran after you edited `app.js`, even though no dependencies changed. What would you change about the `COPY` instruction to prevent this from happening?

---

---

# Scenario 2 -- Running as a Non-Root User

## Objective

Stop the application from running as root and understand concretely what that change protects against.

## What You Will Learn

- What root access inside a container means in practice
- How to create a dedicated system user inside a Docker image
- How to verify that a non-root user genuinely has fewer permissions
- The concept of blast radius reduction

---

## Command Reference

| Command or Flag | What it does |
|---|---|
| `groupadd -r appuser` | Creates a new system group named `appuser`. The `-r` flag designates it as a system group, using a lower GID range reserved for system accounts rather than human users. |
| `useradd -r -g appuser appuser` | Creates a system user named `appuser` assigned to the `appuser` group. `-r` means system account with no home directory. `-g appuser` sets the primary group explicitly. |
| `chown -R appuser:appuser /app` | Changes ownership of `/app` and all contents to `appuser`. `-R` applies the change recursively. Without this, `appuser` cannot read its own application files. |
| `USER appuser` | Dockerfile instruction. Switches the active user. All subsequent Dockerfile instructions and the final running process use this user. |

---

## Step 1 -- Reset the Environment

```bash
docker system prune -af
```

---

## Step 2 -- Create `Dockerfile.nonroot`

Create a file named `Dockerfile.nonroot` inside `docker-labs/` and paste the following:

```dockerfile
# Same base image as Scenario 1
FROM node:20

WORKDIR /app

# Create a dedicated system group and user before copying any files.
# System accounts (-r) have lower numeric IDs and no home directory.
# This user will own and run only this application -- nothing else.
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy files and install dependencies while still operating as root.
# npm install requires write access to system directories that appuser
# would not have, so this must happen before the USER switch.
COPY . .
RUN npm install

# Transfer ownership of everything in /app to appuser.
# Without this, the files are owned by root and appuser cannot read them.
RUN chown -R appuser:appuser /app

# Switch the active user. Every instruction from this point forward --
# including the CMD that starts the server -- runs as appuser.
USER appuser

EXPOSE 3000
CMD ["npm", "start"]
```

---

## Step 3 -- Build and Run

```bash
docker build -f Dockerfile.nonroot -t nonroot-app .
docker run -p 3000:3000 nonroot-app
```

In a second terminal:

```bash
curl http://localhost:3000
```

Expected output:

```
App is running
User ID : 999
Running as : non-root (uid: 999)
Hostname : b7c3d2e1f0a9
```

User ID 999 is not root. The application is running with a restricted, unprivileged identity.

---

## Step 4 -- Verify the Permission Boundary

With the container running, open a shell inside it:

```bash
docker exec -it $(docker ps -q) sh
```

Try to write to a protected system file:

```bash
echo "test" > /etc/passwd
```

Expected:

```
sh: /etc/passwd: Permission denied
```

Try to install a package:

```bash
apt-get install curl
```

Expected:

```
E: Could not open lock file /var/lib/dpkg/lock-frontend - open (13: Permission denied)
```

Try to create a file outside the app directory:

```bash
touch /bin/backdoor
```

Expected:

```
touch: cannot touch '/bin/backdoor': Permission denied
```

Each of these actions is available to root but denied to `appuser`. An attacker who exploits the application now inherits these same restrictions.

Exit and stop the container:

```bash
exit
docker stop $(docker ps -q)
```

---

## Summary -- Scenario 2

You changed one thing: added a dedicated system user and switched to it before the application starts. The application is functionally identical from the outside.

The difference is what an attacker can do if they exploit the application. As root they can read any file, write anywhere on the filesystem, install tools, and attempt to use those tools to escape the container. As `appuser` they are constrained to what that specific, limited user is allowed to do -- which is very little beyond reading the files the application needs.

This is called blast radius reduction. You cannot always prevent a vulnerability from being exploited. You can ensure that when it is, the damage is contained and the attacker's options are limited.

The `.env` file and build tools are still inside the image. Those are the next problems.

---

## Checkpoint

1. Run `docker exec -it $(docker ps -q) whoami` against the running `nonroot-app`. What is printed?
2. Try `cat /app/.env` inside the nonroot container. Can `appuser` read it? What does this tell you about what switching users does and does not protect?
3. Try `apt-get update` inside the container. What error appears and which part of the error message tells you why it failed?

---

## Reflection

- Switching to non-root did not remove the `.env` file from the image. A non-root user can still read files they have permission to access. What is the next logical fix?
- If your application needed to bind to port 80, which requires root privileges on Linux, how would you handle that without running the entire application as root?

---

---

# Scenario 3 -- Protecting Secrets with .dockerignore

## Objective

Prevent sensitive files from ever entering the Docker image in the first place.

## What You Will Learn

- What `COPY . .` actually copies and what it can silently include
- How `.dockerignore` works and why every project needs one
- How to verify a file was excluded from a built image

---

## Command Reference

| Command or Flag | What it does |
|---|---|
| `COPY . .` | Copies all files from the build context directory into the container. Without a `.dockerignore` file this includes secrets, git history, development configs, and anything else present in the folder. |
| `.dockerignore` | A plain text file placed alongside the Dockerfile. Lists file patterns that Docker excludes from the build context before any `COPY` instruction runs. These files are never sent to the Docker daemon and cannot appear in any layer. |
| `docker run --rm` | Starts a container, runs the specified command, then immediately removes the container when it exits. Useful for inspection commands where you do not want a stopped container left behind. |
| `find /app -type f` | Lists all regular files inside `/app` recursively. Use this to inspect exactly which files are present inside an image. |

---

## Step 1 -- Reset the Environment

```bash
docker system prune -af
```

---

## Step 2 -- Create `.dockerignore`

Create a file named `.dockerignore` inside `docker-labs/` and paste the following content exactly:

```
# Git history
# The .git folder contains a complete record of every commit ever made,
# including secrets that were added and later deleted. Removing a file
# from git does not erase it from history -- it remains fully readable
# inside the .git folder.
.git
.gitignore

# Node dependencies
# These are reinstalled fresh during RUN npm install inside the container.
# Including them adds hundreds of megabytes to the build context
# and provides no benefit.
node_modules

# Secrets
# This is the most important section. Files matching any of these patterns
# will never be copied into any image layer. If a .env file reaches
# your image, every credential inside it is readable by anyone
# who can pull the image from a registry.
.env
.env.local
.env.production
.env.*
*.pem
*.key
*.cert
*.p12

# Docker files
# There is no reason to ship the Dockerfile inside the image it produces.
Dockerfile*
docker-compose*
.dockerignore

# Documentation
README.md
*.md

# Operating system metadata files
.DS_Store
Thumbs.db
```

---

## Step 3 -- Rebuild and Inspect

Build using `Dockerfile.nonroot` from Scenario 2, which still uses `COPY . .`:

```bash
docker build -f Dockerfile.nonroot -t secure-copy-app .
```

Inspect exactly which files made it into the image:

```bash
docker run --rm secure-copy-app find /app -type f
```

Expected output:

```
/app/app.js
/app/package.json
/app/package-lock.json
```

The `.env` file is absent. The Dockerfile is absent. Nothing from `.git` is present. Only the files the application needs to run are inside the image.

Confirm the secret cannot be read:

```bash
docker run --rm secure-copy-app cat /app/.env
```

Expected:

```
cat: /app/.env: No such file or directory
```

---

## Step 4 -- Compare Against the Scenario 1 Image

Rebuild the insecure image to compare:

```bash
docker build -f Dockerfile -t insecure-app .
docker run --rm insecure-app find /app -type f
```

You will see `.env` listed alongside the application files. The only difference between the two builds is the presence of `.dockerignore`.

---

## Summary -- Scenario 3

`COPY . .` sends your entire project directory into the image. Without `.dockerignore`, every sensitive file in that directory -- environment files, private keys, certificates, git history -- is bundled silently into an image layer.

`.dockerignore` runs before any `COPY` instruction executes. Files matching its patterns are excluded from the build context before they are ever sent to the Docker daemon. They cannot appear in any image layer because Docker never received them.

The secrets problem is now solved at the source. The image still contains build tools and is large. That is what Scenario 4 addresses.

---

## Checkpoint

1. Run `docker run --rm secure-copy-app find /app -type f`. List every file present. Is `.env` among them?
2. Create a file named `test.pem` in your `docker-labs/` folder, rebuild `secure-copy-app`, and run `find` again. Is `test.pem` present inside the image? Why not?
3. Temporarily remove `.dockerignore` from the folder, rebuild, and run `find`. What files appear that were not there before? Add `.dockerignore` back before continuing.

---

## Reflection

- `.dockerignore` prevents secrets from entering the image at build time. Where should real secrets actually live at runtime in a production system? What Docker features exist for this?
- What team process or CI check would catch a developer accidentally deleting `.dockerignore` before a built image reaches a registry?

---

---

# Scenario 4 -- Multi-Stage Builds

## Objective

Separate the build environment from the runtime environment so that compilers, package managers, and development tools never appear in the final shipped image.

## What You Will Learn

- What a multi-stage build is and the problem it solves
- How to use `COPY --from` to transfer only necessary files between stages
- How to measure and compare image sizes
- What reduced attack surface means in concrete terms

---

## Command Reference

| Command or Flag | What it does |
|---|---|
| `FROM node:20 AS builder` | Starts a new build stage and assigns it the name `builder`. This name is used by `COPY --from` in later stages to reference files produced here. |
| `FROM node:20-slim` | Starts the runtime stage from a slimmed-down variant of the Node.js image. The `slim` variant removes many development packages from the base OS, reducing both size and the number of pre-installed tools. |
| `COPY --from=builder /build/app.js .` | Copies a specific file from the `builder` stage into the current stage. Everything else in `builder` that is not explicitly copied is discarded permanently. |
| `docker images` | Lists all locally available images including name, tag, image ID, creation time, and compressed size on disk. |
| `docker inspect` | Returns detailed JSON metadata about a container or image, including configuration, mounts, network settings, and resource limits. |

---

## Step 1 -- Reset the Environment

```bash
docker system prune -af
```

---

## Step 2 -- Create `Dockerfile.multistage`

Create a file named `Dockerfile.multistage` inside `docker-labs/` and paste the following:

```dockerfile
# ---------------------------------------------------------------
# STAGE 1 -- BUILDER
#
# This stage installs all dependencies and prepares the application.
# It uses the full Node.js image with npm, compilers, and all tools.
# This stage does NOT appear in the final image. Docker discards it
# entirely once the build completes.
# ---------------------------------------------------------------
FROM node:20 AS builder

WORKDIR /build

# Copy package.json before copying source code.
# npm install is only re-run when package.json changes.
# Editing app.js will NOT trigger a reinstall. This is the correct order.
COPY package.json ./

# Install dependencies inside the builder stage.
# npm, the Node.js build toolchain, and all compiled binaries
# remain here and are discarded with this stage.
RUN npm install

# Copy the application source code after dependencies are installed.
COPY app.js .


# ---------------------------------------------------------------
# STAGE 2 -- RUNTIME
#
# This is the only stage that ships to production.
# It starts from a clean, minimal image with no build tools.
# Only files explicitly copied from the builder stage are present.
# ---------------------------------------------------------------
FROM node:20-slim

WORKDIR /app

# Create a non-root user in the clean runtime image.
# Same pattern as Scenario 2.
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy only what the application needs to run.
# The --from=builder flag tells Docker to source these files
# from the builder stage, not from your local filesystem.
# npm, the package cache, compilers, and everything else
# in /build that was not listed here is permanently gone.
COPY --from=builder /build/app.js ./app.js
COPY --from=builder /build/node_modules ./node_modules

# Transfer ownership and switch to non-root user.
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 3000
CMD ["node", "app.js"]
```

---

## Step 3 -- Build All Variants and Compare Sizes

Build all three images so you can compare them in one view:

```bash
docker build -f Dockerfile            -t insecure-app     .
docker build -f Dockerfile.nonroot    -t nonroot-app      .
docker build -f Dockerfile.multistage -t multistage-app   .
```

List them side by side:

```bash
docker images insecure-app nonroot-app multistage-app
```

Expected output (sizes are approximate and will vary slightly):

```
REPOSITORY       TAG      IMAGE ID       CREATED          SIZE
insecure-app     latest   a1b2c3d4e5f6   12 seconds ago   1.10GB
nonroot-app      latest   b2c3d4e5f6a1   10 seconds ago   1.10GB
multistage-app   latest   c3d4e5f6a1b2   7 seconds ago    240MB
```

`insecure-app` and `nonroot-app` are the same size. Adding a non-root user changes who runs the application -- not what the image contains. `multistage-app` is roughly 78 percent smaller because the builder stage, including npm and the full Node.js toolchain, was discarded entirely.

---

## Step 4 -- Verify the Attack Surface Is Reduced

Start the multi-stage container:

```bash
docker run -d -p 3000:3000 multistage-app
```

Open a shell inside it and attempt to use tools that were available in the full image:

```bash
docker exec -it $(docker ps -q) sh
```

```bash
npm --version
```

Expected: `sh: 1: npm: not found`

```bash
curl --version
```

Expected: `sh: 1: curl: not found`

```bash
git --version
```

Expected: `sh: 1: git: not found`

```bash
apt-get install wget
```

Expected: `sh: 1: apt-get: not found`

None of these tools exist in the runtime image. An attacker who gains code execution inside this container cannot use them to download malware, compile attack tools, or interact with external systems.

Exit and stop the container:

```bash
exit
docker stop $(docker ps -q)
```

---

## Step 5 -- Confirm the Application Still Works

```bash
docker run -p 3000:3000 multistage-app
```

```bash
curl http://localhost:3000
```

Expected output:

```
App is running
User ID : 999
Running as : non-root (uid: 999)
Hostname : d4e5f6a1b2c3
```

The application is functionally unchanged. The image is dramatically smaller and the tools available to an attacker are gone.

```bash
docker stop $(docker ps -q)
```

---

## Summary -- Scenario 4

A multi-stage build uses multiple `FROM` instructions in a single Dockerfile. Each `FROM` starts a fresh layer context. Only the final stage becomes the image that gets built, pushed, and run. Everything in earlier stages is discarded.

This means you can use a large, tool-rich image to install dependencies, compile code, run tests, and generate assets -- and then transfer only the finished output into a minimal image that ships to production.

The reduction from 1.1 GB to 240 MB is not only a storage and bandwidth saving. It represents hundreds of removed programs and libraries that an attacker could have used as weapons. A smaller image is also faster to pull, faster to scan for vulnerabilities, and faster to start.

---

## Checkpoint

1. Record the exact sizes shown in `docker images` for `insecure-app` and `multistage-app`. What is the difference in megabytes?
2. List every tool you attempted to use inside `multistage-app` that returned `not found`. Which of these would an attacker find most valuable?
3. Run `curl http://localhost:3000` against `multistage-app`. Does it respond correctly? What does this confirm about removing build tools?

---

## Reflection

- If you needed `curl` available at runtime for health checks, where in the Dockerfile would you add it and how would you limit the risk that adds?
- The builder stage runs during every build even though its output is discarded. If you had a test suite, where would you run it in a multi-stage Dockerfile to ensure failing tests block the build?
- In a system that deploys 50 times per day, what is the practical impact on deployment speed of an image that is 870 MB smaller?

---

---

# Scenario 5 -- Runtime Hardening

## Objective

Apply kernel-level constraints to a running container so that even a fully compromised process has a strictly limited set of available actions.

## What You Will Learn

- What Linux capabilities are and why they matter
- How to restrict filesystem writes at the kernel level
- How to prevent resource exhaustion from a compromised container
- How to block privilege escalation paths from inside a container

---

## Command Reference

| Command or Flag | What it does |
|---|---|
| `--read-only` | Mounts the container root filesystem as read-only. No process inside can write new files, modify binaries, or persist changes anywhere on the filesystem. |
| `--tmpfs /tmp` | Mounts a temporary in-memory filesystem at `/tmp`. Required alongside `--read-only` if the application needs to write any temporary files at runtime. |
| `--memory="128m"` | Sets a hard memory ceiling enforced by the Linux kernel. If the container exceeds this limit, the kernel terminates the process. Prevents a compromised container from exhausting the host's available memory. |
| `--cpus="0.5"` | Limits the container to at most half of one CPU core. Prevents a compromised container from consuming all available compute and degrading other services on the same host. |
| `--cap-drop=ALL` | Removes all Linux capabilities from the container. Containers receive a default subset of roughly 15 capabilities. This flag drops every one of them. |
| `--cap-add=NET_BIND_SERVICE` | Adds a single specific capability back after dropping all others. Use this pattern to grant only what is explicitly needed and nothing more. |
| `--security-opt no-new-privileges:true` | Prevents any process inside the container from gaining more privileges than it started with, even if a setuid binary is present on the filesystem. |
| `docker inspect` | Returns detailed JSON metadata about a running container, including the active resource limits and security options. |

---

## Step 1 -- Reset the Environment

```bash
docker system prune -af
```

---

## Step 2 -- Rebuild the Multi-Stage Image

```bash
docker build -f Dockerfile.multistage -t multistage-app .
```

---

## Step 3 -- Apply Each Flag Individually

Apply each flag on its own first so you can observe exactly what it does before combining them.

**Read-only filesystem:**

```bash
docker run --read-only --tmpfs /tmp -p 3000:3000 multistage-app
```

In a second terminal, try to write a file inside the running container:

```bash
docker exec -it $(docker ps -q) sh -c "echo test > /app/hacked.txt"
```

Expected:

```
sh: /app/hacked.txt: Read-only file system
```

The kernel rejected the write. The attacker cannot persist any file, install any tool, or modify any binary.

Stop the container:

```bash
docker stop $(docker ps -q)
```

**Memory and CPU limits:**

```bash
docker run --memory="128m" --cpus="0.5" -p 3000:3000 multistage-app
```

Verify the limits are registered:

```bash
docker inspect $(docker ps -q) | grep -E '"Memory"|"NanoCpus"'
```

Expected output:

```
"Memory": 134217728,
"NanoCpus": 500000000,
```

134217728 bytes is exactly 128 MB. 500000000 NanoCPUs is exactly 0.5 of one CPU core. These limits are enforced by the Linux kernel cgroup subsystem, not by the application code.

Stop the container:

```bash
docker stop $(docker ps -q)
```

**Dropping Linux capabilities:**

Linux capabilities divide root privilege into approximately 40 distinct units. For example: `CAP_NET_BIND_SERVICE` allows binding to ports below 1024. `CAP_SYS_ADMIN` permits a wide range of administrative operations. `CAP_DAC_OVERRIDE` bypasses standard file permission checks. By default a container receives roughly 15 of these. `--cap-drop=ALL` removes every one.

```bash
docker run --cap-drop=ALL -p 3000:3000 multistage-app
```

Confirm the application still responds:

```bash
curl http://localhost:3000
```

It does. The application requires no special kernel capabilities to serve HTTP traffic via Docker port mapping.

Stop the container:

```bash
docker stop $(docker ps -q)
```

---

## Step 4 -- Run the Fully Hardened Container

Combine all flags into a single command:

```bash
docker run \
  --read-only \
  --tmpfs /tmp \
  --memory="128m" \
  --cpus="0.5" \
  --cap-drop=ALL \
  --security-opt no-new-privileges:true \
  -p 3000:3000 \
  multistage-app
```

The backslash at the end of each line is a line continuation character. It tells the shell the command continues on the next line. This is purely for readability. The command is identical to writing it all on one line.

Confirm the application responds correctly:

```bash
curl http://localhost:3000
```

Expected output:

```
App is running
User ID : 999
Running as : non-root (uid: 999)
Hostname : e5f6a1b2c3d4
```

Stop the container:

```bash
docker stop $(docker ps -q)
```

---

## Summary -- Scenario 5

The Dockerfile controls what is inside the image. Runtime flags control what a running container is permitted to do at the operating system level. These are two separate and complementary layers of defence.

An attacker who bypasses the application layer and achieves code execution inside the container still faces kernel-enforced constraints. A read-only filesystem prevents persistence and tool installation. Memory and CPU limits prevent resource exhaustion attacks against the host. Dropped capabilities remove most avenues for privilege manipulation. `no-new-privileges` blocks setuid-based escalation paths.

Neither layer alone is sufficient. The image must be minimal, the process must be non-root, the filesystem must be locked, and resource limits must be in place. Each layer reduces what is possible when the previous layer fails.

---

## Checkpoint

1. With `--read-only` applied, try `docker exec -it $(docker ps -q) sh -c "touch /tmp/test"`. Does it succeed? Why does `/tmp` behave differently now that `--tmpfs /tmp` is present?
2. Run `docker inspect $(docker ps -q) | grep Memory`. What value is returned? Convert it to megabytes.
3. With `--cap-drop=ALL` applied, try `docker exec -it $(docker ps -q) sh -c "ping 8.8.8.8"`. What happens? Look up which Linux capability `ping` requires to open a raw socket.

---

## Reflection

- You applied these flags on the command line. In a production system using Docker Compose or Kubernetes, where would these constraints be defined so they are always applied consistently?
- If a developer added `--cap-add=SYS_ADMIN` to work around a permission issue without understanding what it grants, what risk would that introduce?
- Runtime hardening protects the host from a compromised container. What additional controls would protect containers from each other on the same host?

---

---

## Full Security Checklist

Use this before pushing any image to a registry.

| Check | How to verify |
|---|---|
| Application runs as non-root | `docker run --rm your-image whoami` must not return `root` |
| Secrets excluded from image | `docker run --rm your-image find /app -type f` must not list `.env` or key files |
| No credentials in image layers | `docker history your-image` -- inspect each layer for sensitive ENV values |
| Multi-stage build in use | `docker images your-image` -- compare size against an equivalent single-stage build |
| Minimal base image used | Dockerfile uses a `-slim`, `-alpine`, or distroless base variant |
| Read-only filesystem at runtime | `--read-only` flag present in the run command or compose definition |
| Resource limits configured | `--memory` and `--cpus` flags present |
| Capabilities dropped | `--cap-drop=ALL` present with `--cap-add` used only for explicitly justified needs |
| Privilege escalation blocked | `--security-opt no-new-privileges:true` present |

---

## The Progression at a Glance

```
Scenario 1  Insecure default
            Runs as root. Ships secrets. Includes all build tools. No limits. ~1.1 GB.

Scenario 2  Non-root user added
            Blast radius reduced if exploited. Secrets still present. ~1.1 GB.

Scenario 3  .dockerignore added
            Secrets excluded from image at build time. Build tools still present. ~1.1 GB.

Scenario 4  Multi-stage build
            Build tools permanently discarded. Minimal runtime image. ~240 MB.

Scenario 5  Runtime hardening
            Kernel-enforced constraints. Read-only filesystem. Resource limits. Capabilities dropped.
```

Each scenario is a meaningful, real improvement. None of them is optional in a production system.

---

## Further Reading

- Docker security best practices: https://docs.docker.com/develop/security-best-practices/
- Distroless images by Google (images with no shell at all): https://github.com/GoogleContainerTools/distroless
- Trivy, open source vulnerability scanner for container images: https://github.com/aquasecurity/trivy
- OWASP Docker Security Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html
- Linux capabilities manual page: https://man7.org/linux/man-pages/man7/capabilities.7.html

---

*Contributions, corrections, and improvements are welcome via issues and pull requests.*
