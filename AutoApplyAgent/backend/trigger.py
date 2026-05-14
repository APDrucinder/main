from workers.pipeline_task import run_pipeline_task

# Pass an actual database user UUID.
USER_ID = "your-user-uuid-here"


if __name__ == "__main__":
    task = run_pipeline_task.delay(USER_ID, "Dhruv_Resume.pdf", ["Bangalore", "Delhi"])
    print(f"Task sent to queue! ID: {task.id}")
