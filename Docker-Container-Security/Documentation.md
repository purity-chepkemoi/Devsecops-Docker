# Docker & Containers - Running Your First Container

Detailed instructions and documentation are available in the GitHub repository:
[https://github.com/samuel-nartey/devops-labs/blob/main/Docker%20%26%20Containers/Running%20Your%20First%20Container/README.md](https://github.com/samuel-nartey/devops-labs/blob/main/Docker%20%26%20Containers/Running%20Your%20First%20Container/README.md)

---

## Scenario 1: The Insecure Default

### Objectives
Understand what a basic Dockerfile looks like, why it is insecure by default, and how Docker layer caching works in practice using timed builds.

### Layer Caching with Timed Builds

**First build -- nothing is cached yet:**
![First Build](Screenshots/Scenario1/first%20buid.png)

**Second build -- nothing has changed:**
![Second Build](Docker-Container-Security/Screenshots/Scenario1/second%20build.png)

**Third build -- simulate a code change:**
![Third Build](Docker-Container-Security/Screenshots/Scenario1/third%20build.png)

### Checkpoint
1.  **Run `docker exec -it $(docker ps -q) whoami` against the running container. What name is printed?**
    ![whoami](Docker-Container-Security/Screenshots/Scenario1/whoami.png)
    * **Answer:** `root`. This means the process inside the container is running with root privileges (UID 0). By default, this is a security risk. If a process running as root is compromised, an attacker may have full control over the container environment and could potentially attempt "container breakout" techniques to access the host system.

2.  **Look at your first and second build outputs. How many seconds did each take? How many layers showed CACHED on the second run?**
    | Build Run | Real Time | Cached Layers |
    | :--- | :--- | :--- |
    | First Build | 42.326s | 0 |
    | Second Build | 4.312s | 4 |

3.  **In the third build after editing app.js, which was the first layer that was NOT pulled from cache? What was the layer immediately below it that WAS cached?**
    * **First layer NOT cached:** The `COPY . .` layer. Because you modified a file in the directory, the hash of that layer changed, invalidating the cache for that step and all subsequent steps.
    * **Layer below that WAS cached:** The `WORKDIR /app` layer remained cached, as it does not depend on the content of your local files.

### Reflection
* **Secret Exposure:** If an image contained real AWS access keys in `.env` and was pushed to a public repository, bots would likely scrape and abuse them within seconds or minutes.
    ![Secrets Step 4](Docker-Container-Security/Screenshots/Scenario1/step4.png)
* **Cache Optimization:** To prevent `npm install` from re-running every time code changes, copy only `package.json` and `package-lock.json` first, run `npm install`, then copy the rest of the application code.

---

## Scenario 2: Running as a Non-Root User

### Objective
Stop the application from running as root and understand concretely what that change protects against.

### Build and Run
![Build and Run](Docker-Container-Security/Screenshots/Scenario2/build%20and%20run.png)

### Verify the Permission Boundary
![Verify Permissions](Docker-Container-Security/Screenshots/Scenario2/verify.png)

### Checkpoint
1.  **Run `docker exec -it $(docker ps -q) whoami` against the running nonroot-app. What is printed?**
    ![Checkpoint](Docker-Container-Security/Screenshots/Scenario2/checkpoint.png)
    * **Answer:** `appuser`. This confirms that the process is no longer executing with root privileges.

2.  **Try `cat /app/.env` inside the nonroot container. Can appuser read it?**
    * **Answer:** Yes, appuser can read it. This tells you that switching users protects the system from arbitrary modifications (like installing packages), but does not inherently protect sensitive data embedded in the image if permissions allow the user to read the file.

3.  **Try `apt-get update` inside the container. What error appears?**
    * **Answer:** `(13: Permission denied)`. This shows `appuser` lacks write permissions to modify system directories owned by root.

---

## Scenario 3: Protecting Secrets with .dockerignore

### Objective
Prevent sensitive files from ever entering the Docker image in the first place.

### Rebuild and Inspect
![Build](Docker-Container-Security/Screenshots/Scenario3/build.png)
![Run](Docker-Container-Security/Screenshots/Scenario3/run.png)

### Checkpoint
1.  **Run `docker run --rm secure-copy-app find /app -type f`. List every file present. Is .env among them?**
    ![Checkpoint](Docker-Container-Security/Screenshots/Scenario3/checkpoint.png)
    * **Answer:** No. `.dockerignore` correctly prevents the file from being copied during the `COPY . .` instruction.

2.  **Create a file named `test.pem`, rebuild, and run find again. Is `test.pem` present?**
    * **Answer:** No, if it is listed in `.dockerignore`.
    ![Step 4a](Docker-Container-Security/Screenshots/Scenario3/step4a.png)

3.  **Temporarily remove `.dockerignore`, rebuild, and run find. What files appear?**
    ![Step 4b](Docker-Container-Security/Screenshots/Scenario3/step4b.png)
    * **Answer:** `.env`, `test.pem`, and other previously excluded files will now appear.

### Reflection
* **Runtime Secrets:** Real secrets should live in environment variables, secret management systems (Vault, AWS Secrets Manager), or Docker Secrets (Swarm/Kubernetes).
* **CI/CD Safety:** Implement pipeline linting, image scanning (Trivy, Snyk), and mandatory PR reviews to catch accidental deletion of `.dockerignore`.

---

## Scenario 4: Multi-Stage Builds

### Objective
Separate the build environment from the runtime environment to reduce the attack surface and image size.

### Build Failures and Fixes
During initial builds, failures occurred due to missing dependencies in `package.json` and incompatible commands in Alpine Linux.

![Original JSON](Docker-Container-Security/Screenshots/Scenario4/json1.png)
![Edited JSON](Docker-Container-Security/Screenshots/Scenario4/json2.png)
![Build Error](Docker-Container-Security/Screenshots/Scenario4/Error.png)
![Alpine Error](Docker-Container-Security/Screenshots/Scenario4/err.png)

### Build and Comparison
![Multi-stage Build](Docker-Container-Security/Screenshots/Scenario4/build.png)
![Image Sizes](Docker-Container-Security/Screenshots/Scenario4/sizes.png)

### Checkpoint
1.  **Exact sizes shown in `docker images`:**
    * `insecure-app`: 1.59 GB
    * `multistage-app`: 193 MB
    * **Difference:** ~1.4 GB reduction.

2.  **Tools missing in `multistage-app`:**
    ![Reduced Attack Surface](Docker-Container-Security/Screenshots/Scenario4/attacksurface.png)
    * **Answer:** `curl`, `git`, `apt`. `curl` is most valuable to an attacker for probing networks and downloading payloads.

3.  **Confirm the Application Still Works:**
    ![App Working](Docker-Container-Security/Screenshots/Scenario4/appworking.png)
    * **Answer:** The app responds correctly, confirming that removing build tools does not break runtime functionality.

---

## Scenario 5: Runtime Hardening

### Objective
Apply kernel-level constraints to a running container.

### Build and Run
![Build](Docker-Container-Security/Screenshots/Scenario5/build.png)
![Individual Flags](Docker-Container-Security/Screenshots/Scenario5/run.png)

### Checkpoint
1.  **With `--read-only` and `--tmpfs /tmp` applied, does `touch /tmp/test` succeed?**
    ![Step 4a](Docker-Container-Security/Screenshots/Scenario5/step4a.png)
    * **Answer:** Yes. The explicit `tmpfs` mount at `/tmp` provides a writable layer that overrides the global read-only constraint for that specific path.

2.  **Run `docker inspect $(docker ps -q) | grep Memory`. What is the value?**
    ![Inspect](Docker-Container-Security/Screenshots/Scenario5/inspect.png)
    * **Answer:** `134217728` bytes, which equals **128 MB**.

3.  **With `--cap-drop=ALL` applied, try `ping 8.8.8.8`. What happens?**
    ![Step 4b](Docker-Container-Security/Screenshots/Scenario5/step4b.png)
    * **Answer:** It fails with "Permission denied". `ping` requires `CAP_NET_RAW` to open raw sockets, which was stripped.

### Final Verification
![Fully Hardened Run](Docker-Container-Security/Screenshots/Scenario5/stillworking%20app.png)

### Reflection
* **Orchestration:** Constraints should be defined in `docker-compose.yml` under `deploy` resources or Kubernetes `securityContext`.
* **SYS_ADMIN Risk:** Adding `SYS_ADMIN` provides near-root access to the kernel, allowing container escapes.
* **Inter-container Security:** Use Network Policies, User Namespaces, and specialized runtimes like gVisor or Kata Containers.

---

### References
[https://github.com/samuel-nartey/devops-labs/tree/main/Docker%20%26%20Containers/Running%20Your%20First%20Container](https://github.com/samuel-nartey/devops-labs/tree/main/Docker%20%26%20Containers/Running%20Your%20First%20Container)
