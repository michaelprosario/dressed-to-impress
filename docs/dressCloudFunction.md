# Serverless Virtual Try-on: Demystifying Google Cloud Functions with Clean Architecture

Have you ever wondered how to take local Python logic and run it in the cloud as an automated worker?

In our previous post, we explored how the `dress` CLI operates locally. Today, we're taking a giant leap into the cloud. We will explore [gcp_function/main.py](file:///home/user/dressed-to-impress/gcp_function/main.py)—the entry point for our Google Cloud Function—to see how we can trigger virtual try-on requests and image uploads in a serverless environment.

Because we followed **Clean Architecture** guidelines, we didn't have to change a single line of our core try-on logic to run in the cloud. Let's look at how this is done!

---

## 1. What is a Serverless Cloud Function?

Normally, to run code on the web, you need to set up a server, configure ports, manage operating system updates, and keep the server running 24/7.

**Serverless Computing** (specifically Functions-as-a-Service or FaaS) changes this. With Google Cloud Functions, you write a single Python function and upload it to Google. Google handles the servers:
- If no requests are coming in, zero servers run (saving you money).
- When a request comes in, Google instantly boots up a micro-container, runs your code, returns the answer, and shuts it down.

---

## 2. Exploring [gcp_function/main.py](file:///home/user/dressed-to-impress/gcp_function/main.py)

Let's dissect the code that connects this cloud trigger to our inner business logic.

### Step 2.1: The Trigger Types
A Cloud Function can be triggered in different ways. In [main.py](file:///home/user/dressed-to-impress/gcp_function/main.py), we implement two types of triggers:

#### A. HTTP POST Trigger (Direct HTTP Requests)
We use HTTP triggers for direct request-response actions, like when a client wants to upload a file:
```python
@functions_framework.http
def upload_handler(request):
    # Process HTTP request file upload
```
This receives a Flask `Request` object. We read files uploaded via multipart form data (`request.files['file']`), package them into an `UploadImageCommand`, and run the use case.

#### B. CloudEvent Trigger (Asynchronous Queue Messages)
For virtual try-on executions, we don't want the user to wait around for a slow AI image generation request. Instead, we use a message queue (Google Cloud Pub/Sub) to handle them asynchronously:
```python
@functions_framework.cloud_event
def dress_pubsub_handler(cloud_event) -> None:
    # Read message data from queue and execute try-on
```
When a message is placed in a Pub/Sub topic, Google automatically triggers this function. The payload is base64-encoded, so we decode it, parse the JSON, and run the try-on in the background.

---

## 3. Key Cloud Engineering Concepts Explained

Here are the crucial concepts that make this Cloud Function run cleanly and remain easy to debug:

### Concept 3.1: Lazy Initialization (The Composition Root)
Booting up a container in serverless computing takes time (this is called a **Cold Start**). If we instantiate databases, API clients, and repositories at the top level of our script, every single function startup will be slow.

To optimize performance, we initialize our dependencies **lazily** (only when they are first needed):
```python
_cloud_use_case = None

def get_cloud_use_case() -> CloudDressUseCase:
    global _cloud_use_case
    if _cloud_use_case is None:
        blob_repo = GcsBlobRepository()
        local_repo = FilesystemImageRepository()
        gemini_provider = GeminiImageProvider(api_key=GEMINI_API_KEY)
        
        dress_use_case = DressUseCase(repo=local_repo, provider=gemini_provider)
        _cloud_use_case = CloudDressUseCase(...)
    return _cloud_use_case
```
If a function container stays warm (handles multiple requests in a row), it reuses the pre-initialized `_cloud_use_case` global variable instantly, saving computation and connection times!

### Concept 3.2: Structured Cloud Logging
In a local terminal, you can print errors directly to the screen. In the cloud, prints are lost in massive logs.
We configure standard Python logging to output structured strings to standard output:
```python
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
```
Google Cloud Logging automatically monitors standard output (`sys.stdout`) and parses these logs, indexing them by severity levels (`INFO`, `WARNING`, `ERROR`). If a task fails, we can filter for `severity=ERROR` in Cloud Logging to instantly find tracebacks and debug issues.

### Concept 3.3: Temporary File Lifecycle & Cleanups
Google Cloud Functions run in a read-only environment, except for the `/tmp` folder which behaves like a temporary local drive. However, `/tmp` is actually stored in the instance's RAM (memory).

If we download images, process them, and forget to delete them, the function's memory will eventually fill up, causing execution crashes!
To solve this, we wrap our code in a `try...finally` block:
```python
try:
    # 1. Download blobs to /tmp/dress_<uuid>
    # 2. Run try-on
    # 3. Upload to GCS
finally:
    # 4. Safe cleanup
    shutil.rmtree(work_dir, ignore_errors=True)
```
This guarantees that no matter whether the try-on succeeds or raises an error, the local folder is completely cleaned up, keeping our container memory footprint low.

---

## 4. Summary

Moving code to the cloud shouldn't mean rewriting it. By dividing our project into clean architectural boundaries:
1. The **Core Use Cases** orchestrate tasks using pure interfaces.
2. The **Google Cloud Function** simply acts as an outer delivery wrapper, receiving incoming messages and triggering our clean core services.

With this structure, you can adapt your application to any platform—from local consoles to serverless pipelines—with ease. Happy coding!
