from workers.pipeline_task import run_pipeline_task

task = run_pipeline_task.delay({task.id},"Dhruv_Resume.pdf", ["Bangalore", "Delhi"])
print(f"Task sent to queue! ID: {task.id}")