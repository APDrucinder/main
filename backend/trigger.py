from workers.pipeline_task import run_pipeline_task

# Pass the actual user_id (UUID from your database) as the first argument
USER_ID = "your-user-uuid-here"

task = run_pipeline_task.delay(USER_ID, "Dhruv_Resume.pdf", ["Bangalore", "Delhi"])
print(f"Task sent to queue! ID: {task.id}")