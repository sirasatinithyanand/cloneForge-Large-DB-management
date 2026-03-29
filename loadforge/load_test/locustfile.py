"""
Locust load test for LoadForge.
Run: locust -f load_test/locustfile.py --host=http://localhost:8000
Then open http://localhost:8089 to start the test.
"""
import random
from locust import HttpUser, task, between


class LoadForgeUser(HttpUser):
    wait_time = between(0.5, 2)

    def on_start(self):
        # Each simulated user picks a random tenant (1-5)
        self.tenant_id = random.randint(1, 5)

    @task(4)
    def dashboard(self):
        with self.client.get(
            f"/dashboard?tenant_id={self.tenant_id}",
            name="/dashboard",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                qt = data.get("query_time_ms", 0)
                if qt > 500:
                    resp.failure(f"Slow query: {qt}ms")
                else:
                    resp.success()

    @task(3)
    def transactions(self):
        status = random.choice(["success", "pending", "failed"])
        self.client.get(
            f"/transactions?tenant_id={self.tenant_id}&status={status}",
            name="/transactions",
        )

    @task(1)
    def report(self):
        with self.client.get(
            f"/report?tenant_id={self.tenant_id}",
            name="/report",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                qt = data.get("query_time_ms", 0)
                if qt > 2000:
                    resp.failure(f"Very slow report: {qt}ms")
                else:
                    resp.success()

    @task(2)
    def paginated_transactions(self):
        self.client.get(
            f"/transactions?tenant_id={self.tenant_id}&limit=20",
            name="/transactions (paginated)",
        )
