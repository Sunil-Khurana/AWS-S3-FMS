import os
import threading
import boto3
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime, timezone

# ------------------- S3 Helper Functions -------------------

def list_objects(bucket_name):
    s3 = boto3.client("s3")
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket_name):
        for obj in page.get("Contents", []):
            yield obj["Key"], obj["Size"], obj["LastModified"]

def download_file(bucket_name, key, local_path):
    s3 = boto3.client("s3")
    s3.download_file(bucket_name, key, local_path)

def upload_file(bucket_name, local_path, key):
    s3 = boto3.client("s3")
    s3.upload_file(local_path, bucket_name, key)

def delete_object(bucket_name, key):
    s3 = boto3.client("s3")
    s3.delete_object(Bucket=bucket_name, Key=key)

def rename_object(bucket_name, old_key, new_key):
    s3 = boto3.client("s3")
    s3.copy_object(Bucket=bucket_name, CopySource={"Bucket": bucket_name, "Key": old_key}, Key=new_key)
    s3.delete_object(Bucket=bucket_name, Key=old_key)

# ------------------- Compare Folder & S3 -------------------

def compare_local_and_s3(bucket_name, local_folder, prefix=""):
    s3 = boto3.client("s3")
    s3_objects = {}
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix):
        for obj in page.get("Contents", []):
            s3_objects[obj["Key"]] = {
                "size": obj["Size"],
                "last_modified": obj["LastModified"].astimezone(timezone.utc)
            }

    local_files = {}
    for root, _, files in os.walk(local_folder):
        for f in files:
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, start=local_folder).replace("\\", "/")
            stat = os.stat(full_path)
            local_files[rel_path] = {
                "size": stat.st_size,
                "mtime": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
            }

    results = []
    all_keys = sorted(set(local_files.keys()) | set(s3_objects.keys()))
    for key in all_keys:
        if key not in local_files:
            results.append((key, "📁 Missing in Local"))
        elif key not in s3_objects:
            results.append((key, "☁️ Missing in S3"))
        else:
            lf = local_files[key]
            sf = s3_objects[key]
            if lf["size"] == sf["size"]:
                results.append((key, "✅ Matched"))
            elif lf["mtime"] > sf["last_modified"]:
                results.append((key, "⬆️ Newer in Local"))
            else:
                results.append((key, "⬇️ Newer in S3"))
    return results

# ------------------- GUI -------------------

class CloudDockApp:
    def __init__(self, root):
        self.root = root
        self.root.title("CloudDock v6 — Compare Edition")
        self.root.geometry("900x600")

        self.current_bucket = tk.StringVar()
        self._build_ui()

    def _build_ui(self):
        top_frame = ttk.Frame(self.root, padding=5)
        top_frame.pack(fill="x")

        ttk.Label(top_frame, text="S3 Bucket:").pack(side="left")
        self.bucket_entry = ttk.Entry(top_frame, textvariable=self.current_bucket, width=40)
        self.bucket_entry.pack(side="left", padx=5)
        ttk.Button(top_frame, text="List Objects", command=self._list_objects_thread).pack(side="left", padx=2)

        # Treeview for files
        self.tree = ttk.Treeview(self.root, columns=("Size", "LastModified"), show="headings")
        self.tree.heading("Size", text="Size (Bytes)")
        self.tree.heading("LastModified", text="Last Modified (UTC)")
        self.tree.column("Size", width=120)
        self.tree.column("LastModified", width=200)
        self.tree.pack(fill="both", expand=True, pady=5)

        # Actions
        right_frame = ttk.Frame(self.root, padding=5)
        right_frame.pack(fill="x")
        ttk.Button(right_frame, text="Upload File", command=self._upload_thread).pack(side="left", padx=4)
        ttk.Button(right_frame, text="Download File", command=self._download_thread).pack(side="left", padx=4)
        ttk.Button(right_frame, text="Delete File", command=self._delete_thread).pack(side="left", padx=4)
        ttk.Button(right_frame, text="Rename File", command=self._rename_thread).pack(side="left", padx=4)
        ttk.Button(right_frame, text="Compare Folder & S3", command=self._compare_folder_thread).pack(side="left", padx=4)

        # Log area
        self.log = tk.Text(self.root, height=8)
        self.log.pack(fill="x", padx=5, pady=5)

    def _log(self, text):
        self.log.insert("end", text + "\n")
        self.log.see("end")

    # ---------------- Threads ----------------
    def _list_objects_thread(self):
        threading.Thread(target=self.list_objects).start()

    def _upload_thread(self):
        threading.Thread(target=self.upload_file).start()

    def _download_thread(self):
        threading.Thread(target=self.download_file).start()

    def _delete_thread(self):
        threading.Thread(target=self.delete_file).start()

    def _rename_thread(self):
        threading.Thread(target=self.rename_file).start()

    def _compare_folder_thread(self):
        threading.Thread(target=self.compare_folder_with_s3).start()

    # ---------------- Actions ----------------
    def list_objects(self):
        bucket = self.current_bucket.get().strip()
        if not bucket:
            messagebox.showerror("Error", "Enter bucket name")
            return
        self._log(f"Listing objects in {bucket} ...")
        self.tree.delete(*self.tree.get_children())
        try:
            for key, size, modified in list_objects(bucket):
                self.tree.insert("", "end", values=(key, size, modified))
            self._log("List complete.")
        except Exception as e:
            messagebox.showerror("Error", str(e))
            self._log(f"Error: {e}")

    def upload_file(self):
        bucket = self.current_bucket.get().strip()
        if not bucket:
            return
        file_path = filedialog.askopenfilename()
        if not file_path:
            return
        key = os.path.basename(file_path)
        self._log(f"Uploading {key} to {bucket}...")
        try:
            upload_file(bucket, file_path, key)
            self._log("Upload complete.")
        except Exception as e:
            messagebox.showerror("Error", str(e))
            self._log(f"Error: {e}")

    def download_file(self):
        bucket = self.current_bucket.get().strip()
        selected = self.tree.selection()
        if not bucket or not selected:
            return
        key = self.tree.item(selected[0])["values"][0]
        save_path = filedialog.asksaveasfilename(initialfile=key)
        if not save_path:
            return
        self._log(f"Downloading {key} from {bucket}...")
        try:
            download_file(bucket, key, save_path)
            self._log("Download complete.")
        except Exception as e:
            messagebox.showerror("Error", str(e))
            self._log(f"Error: {e}")

    def delete_file(self):
        bucket = self.current_bucket.get().strip()
        selected = self.tree.selection()
        if not bucket or not selected:
            return
        key = self.tree.item(selected[0])["values"][0]
        if messagebox.askyesno("Confirm", f"Delete {key}?"):
            self._log(f"Deleting {key}...")
            try:
                delete_object(bucket, key)
                self._log("Deleted successfully.")
                self.list_objects()
            except Exception as e:
                messagebox.showerror("Error", str(e))
                self._log(f"Error: {e}")

    def rename_file(self):
        bucket = self.current_bucket.get().strip()
        selected = self.tree.selection()
        if not bucket or not selected:
            return
        old_key = self.tree.item(selected[0])["values"][0]
        new_key = simple_input_dialog(self.root, "Rename File", f"Enter new name for {old_key}:")
        if not new_key:
            return
        self._log(f"Renaming {old_key} → {new_key}...")
        try:
            rename_object(bucket, old_key, new_key)
            self._log("Renamed successfully.")
            self.list_objects()
        except Exception as e:
            messagebox.showerror("Error", str(e))
            self._log(f"Error: {e}")

    def compare_folder_with_s3(self):
        bucket = self.current_bucket.get().strip()
        local_folder = filedialog.askdirectory(title="Select Local Folder to Compare")
        if not bucket or not local_folder:
            return
        self._log(f"Comparing local folder '{local_folder}' with bucket '{bucket}' ...")
        try:
            results = compare_local_and_s3(bucket, local_folder)
            report = "\n".join([f"{status:20} {key}" for key, status in results])
            self._log("Comparison complete.")

            top = tk.Toplevel(self.root)
            top.title("Comparison Results")
            txt = tk.Text(top, wrap="none", width=120, height=40)
            txt.insert("1.0", report)
            txt.pack(fill="both", expand=True)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            self._log(f"Error: {e}")

# ------------------- Utility Dialog -------------------

def simple_input_dialog(parent, title, prompt):
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    ttk.Label(dialog, text=prompt).pack(padx=10, pady=10)
    entry = ttk.Entry(dialog, width=40)
    entry.pack(padx=10, pady=5)
    entry.focus_set()
    value = {}

    def on_ok():
        value["text"] = entry.get()
        dialog.destroy()

    ttk.Button(dialog, text="OK", command=on_ok).pack(pady=5)
    dialog.wait_window()
    return value.get("text")

# ------------------- Main -------------------

if __name__ == "__main__":
    root = tk.Tk()
    app = CloudDockApp(root)
    root.mainloop()
