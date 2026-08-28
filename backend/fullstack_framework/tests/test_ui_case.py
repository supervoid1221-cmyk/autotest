import pytest

from fullstack_framework.commons.ui_executor import execute_ui_case, load_ui_cases


ui_cases, ui_case_names = load_ui_cases()


@pytest.mark.parametrize("ui_case", ui_cases, ids=ui_case_names)
def test_ui_case(ui_case):
    execute_ui_case(ui_case)
