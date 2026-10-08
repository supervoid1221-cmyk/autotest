from .runner import execute_run


def run_performance_test(run_id, tenant_id=None):
    execute_run(run_id, tenant_id)
