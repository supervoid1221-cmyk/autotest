"""页面语义定位、评分及歧义保护。

所有自动定位都必须得到唯一且高置信度的候选；否则抛出携带候选详情的错误，
交给用户补充页面元素描述或手动兜底表达式。
"""
from dataclasses import dataclass, field
import time
import uuid

from .fingerprints import similarity
from .normalizer import normalize, semantic_context_tokens, semantic_terms


class SmartLocatorError(ValueError):
    def __init__(self, message, candidates=None):
        self.candidates = candidates or []
        super().__init__(message)


@dataclass
class Candidate:
    locator: object
    strategy: str
    score: int
    phrase: str
    semantic: bool = False
    detail: dict = field(default_factory=dict)


INPUT_ACTIONS = {"input", "clear", "save_text", "assert_value"}
TEXT_ACTIONS = {"assert_visible", "assert_text"}
CLICKABLE_SELECTOR = "button, a, input[type='button'], input[type='submit'], [role='button'], [role='link'], [role='tab'], [role='menuitem'], [onclick]"
EDITABLE_SELECTOR = "input, textarea, select, [contenteditable='true'], [role='textbox'], [role='combobox']"
FORM_CONTROL_SELECTOR = "input:not([type='hidden']), textarea, select, button, [contenteditable='true'], [role='textbox'], [role='combobox']"
FALLBACK_STRATEGIES = {
    "nearby_form_field", "form_label_following_control", "fuzzy_accessible_name",
    "semantic_input_type", "native_select", "role_combobox", "role_checkbox", "role_radio",
    "indexed_nearby_field", "indexed_fuzzy", "indexed_semantic_type",
}
DIALOG_SCOPE_SELECTOR = (
    'dialog[open], [role="dialog"], [aria-modal="true"], '
    '.driver-popover, .ant-modal, .el-dialog, .v-dialog, '
    '[class*="modal" i], [class*="dialog" i], [class*="drawer" i]'
)
def _config(step):
    options = getattr(step, "options", None) or {}
    value = options.get("smart_locator", {}) if isinstance(options, dict) else {}
    if not isinstance(value, dict):
        return {}
    environment = str(getattr(step, "environment_name", "") or "")
    overrides = value.get("environments", {})
    override = overrides.get(environment, {}) if isinstance(overrides, dict) else {}
    if not isinstance(override, dict):
        override = {}
    merged = {key: item for key, item in value.items() if key != "environments"}
    base_aliases = merged.get("aliases", [])
    env_aliases = override.get("aliases", [])
    if isinstance(base_aliases, str):
        base_aliases = [base_aliases]
    if isinstance(env_aliases, str):
        env_aliases = [env_aliases]
    merged.update(override)
    merged["aliases"] = [*base_aliases, *env_aliases]
    return merged


def _add(candidates, locator, strategy, score, phrase, semantic=False):
    candidates.append(Candidate(locator, strategy, score, phrase, semantic))


def _nearby_field_candidates(page, phrase):
    """由字段标题的空间位置反查其控件，兼容无 label/for 的自定义表单。

    很多管理后台把“代理”渲染为普通 div，并在其下方放一个 role=combobox 的
    自定义下拉框；这种结构无法由 get_by_label 识别。这里仅接受标题附近的
    输入/下拉类控件，绝不把后续普通链接或按钮当作字段值。
    """
    target = normalize(phrase)
    if not target:
        return []
    try:
        controls = page.locator(FORM_CONTROL_SELECTOR)
        total = min(controls.count(), 120)
    except Exception:
        return []
    discovered = []
    for index in range(total):
        locator = controls.nth(index)
        try:
            distance = locator.evaluate("""(element, target) => {
                const compact = (value) => String(value || '').normalize('NFKC').trim().toLowerCase()
                  .replace(/[\\s_\\-:/：()（）,.，。]+/g, '');
                const control = element.getBoundingClientRect();
                if (!control.width || !control.height) return -1;
                let closest = Infinity;
                for (const label of document.querySelectorAll('label, span, div, p, dt, strong, b')) {
                    if (label === element || compact(label.innerText) !== target) continue;
                    const box = label.getBoundingClientRect();
                    if (!box.width || !box.height) continue;
                    const vertical = control.top - box.bottom;
                    const horizontalGap = Math.max(0, Math.max(box.left, control.left) - Math.min(box.right, control.right));
                    // 标题可在控件上方或左侧；限制距离避免跨表单误配。
                    if (vertical < -36 || vertical > 220 || horizontalGap > 220) continue;
                    closest = Math.min(closest, Math.abs(vertical) + horizontalGap * 0.35);
                }
                return Number.isFinite(closest) ? closest : -1;
            }""", target)
            if distance >= 0:
                discovered.append((float(distance), Candidate(
                    locator, "nearby_form_field", max(50, round(55 - min(float(distance), 180) / 18)), phrase,
                )))
        except Exception:
            continue
    if not discovered:
        return []
    discovered.sort(key=lambda item: item[0])
    nearest_distance = discovered[0][0]
    # 一个字段标题只关联最近控件；只有几乎同距时才保留多个，让后续歧义保护处理。
    return [candidate for distance, candidate in discovered if distance <= nearest_distance + 2]


def _candidates(page, action, target, configuration):
    phrases, input_types = semantic_terms(target, configuration)
    candidates = []
    exact_target = str(target or "").strip()
    test_id = str(configuration.get("test_id") or "").strip()
    role = str(configuration.get("role") or "").strip()

    if test_id:
        _add(candidates, page.get_by_test_id(test_id), "test_id", 100, test_id)

    for phrase in phrases:
        is_semantic = normalize(phrase) != normalize(exact_target)
        bonus = -12 if is_semantic else 0
        if action in INPUT_ACTIONS | TEXT_ACTIONS | {"select", "check", "uncheck"}:
            _add(candidates, page.get_by_label(phrase, exact=True), "label", 95 + bonus, phrase, is_semantic)
            _add(candidates, page.get_by_placeholder(phrase, exact=True), "placeholder", 88 + bonus, phrase, is_semantic)
            _add(candidates, page.get_by_role("textbox", name=phrase, exact=True), "role_textbox", 92 + bonus, phrase, is_semantic)
            _add(candidates, page.locator(f'[aria-label="{phrase}"]'), "aria_label", 90 + bonus, phrase, is_semantic)
            _add(candidates, page.locator(f'[name="{phrase}"]'), "name", 82 + bonus, phrase, is_semantic)
            _add(candidates, page.locator(f'[id="{phrase}"]'), "id", 82 + bonus, phrase, is_semantic)
            # “请输入用户名”是对“用户名”的强语义命中，应优先于空间邻近兜底。
            semantic_score = 82 if is_semantic else 84
            _add(candidates, page.get_by_label(phrase, exact=False), "label_contains", semantic_score, phrase, is_semantic)
            _add(candidates, page.get_by_placeholder(phrase, exact=False), "placeholder_contains", semantic_score - 4, phrase, is_semantic)
            # 自定义组件经常没有 label/for，只能根据字段标题与控件的空间关系定位。
            candidates.extend(_nearby_field_candidates(page, phrase))

        if action in {"click", "assert_visible", "assert_text"}:
            # 表单标题本身通常不可点击；优先尝试其语义关联的控件，并在没有
            # label/for 关联的页面中兜底寻找标题后的第一个可交互控件。
            _add(candidates, page.get_by_label(phrase, exact=True), "label_control", 91 + bonus, phrase, is_semantic)
            _add(
                candidates,
                page.get_by_text(phrase, exact=True).locator(
                    "xpath=following::*[self::input or self::textarea or self::select "
                    "or @role='combobox' or @role='textbox'][1]"
                ),
                # 这是无 label/for 结构时的最后兜底，不能与精确菜单/按钮同级，
                # 否则“账号管理”会错误牵连到页面后续的普通链接。
                "form_label_following_control", 68 + bonus, phrase, is_semantic,
            )
            candidates.extend(_nearby_field_candidates(page, phrase))
            # 用户填写的是页面可见文字时，优先点击承载该文字的菜单/按钮；这比仅靠
            # aria-label 命中的图标按钮更符合意图（例如“公告”菜单与顶部通知铃铛）。
            _add(
                candidates,
                page.get_by_text(phrase, exact=True).locator(
                    "xpath=ancestor-or-self::*[self::button or self::a or @role='button' or @role='link'][1]"
                ),
                "text_clickable_ancestor", 98 + bonus, phrase, is_semantic,
            )
            _add(candidates, page.get_by_role("link", name=phrase, exact=True), "role_link", 94 + bonus, phrase, is_semantic)
            _add(candidates, page.get_by_role("button", name=phrase, exact=True), "role_button", 92 + bonus, phrase, is_semantic)
            _add(candidates, page.get_by_text(phrase, exact=True), "text", 86 + bonus, phrase, is_semantic)
            _add(candidates, page.get_by_role("button", name=phrase, exact=False), "role_button_contains", 84 if is_semantic else 62, phrase, is_semantic)
            _add(candidates, page.get_by_text(phrase, exact=False), "text_contains", 54 + bonus, phrase, is_semantic)

    if role:
        _add(candidates, page.get_by_role(role, name=exact_target or None, exact=bool(exact_target)), "configured_role", 96, role)

    # HTML 属性是通用语义提示；是否自动选中仍由唯一性与评分控制。
    for input_type in input_types:
        if action in INPUT_ACTIONS | {"select", "check", "uncheck"}:
            _add(candidates, page.locator(f'input[type="{input_type}"]'), "semantic_input_type", 58, input_type, True)
        if action == "click" and input_type == "submit":
            _add(candidates, page.locator('button[type="submit"], input[type="submit"]'), "semantic_submit", 58, input_type, True)
    if action == "select":
        _add(candidates, page.locator("select"), "native_select", 35, "select")
        _add(candidates, page.get_by_role("combobox"), "role_combobox", 40, "combobox")
    if action in {"check", "uncheck"}:
        _add(candidates, page.get_by_role("checkbox"), "role_checkbox", 40, "checkbox")
        _add(candidates, page.get_by_role("radio"), "role_radio", 40, "radio")
    return candidates


def _element_info(locator):
    return locator.evaluate("""element => {
        const style = getComputedStyle(element), box = element.getBoundingClientRect();
        return {
            tag: element.tagName.toLowerCase(),
            type: (element.getAttribute('type') || '').toLowerCase(),
            role: element.getAttribute('role') || '',
            id: element.id || '', name: element.getAttribute('name') || '',
            testId: element.getAttribute('data-testid') || '',
            ariaLabel: element.getAttribute('aria-label') || '',
            text: (element.innerText || '').trim().slice(0, 120),
            value: (element.getAttribute('value') || '').trim().slice(0, 120),
            placeholder: element.getAttribute('placeholder') || '',
            clickable: !!element.getAttribute('onclick') || element.tabIndex >= 0
                || ['button', 'a'].includes(element.tagName.toLowerCase())
                || ['button', 'link', 'tab', 'menuitem'].includes(element.getAttribute('role') || ''),
            disabled: !!element.disabled,
            editable: !!element.isContentEditable,
            visible: style.display !== 'none' && style.visibility !== 'hidden'
                && Number(style.opacity || 1) !== 0 && box.width > 0 && box.height > 0,
            x: box.x, y: box.y,
            inDialog: !!element.closest('[role="dialog"], dialog, [aria-modal="true"]'),
            dialogLabel: (element.closest('[role="dialog"], dialog, [aria-modal="true"]') || {}).getAttribute?.('aria-label') || ''
        };
    }""")


def _compatible(action, info):
    tag, element_type, role = info["tag"], info["type"], info["role"]
    if action in INPUT_ACTIONS:
        return (tag == "textarea" or info["editable"] or role in {"textbox", "searchbox", "combobox"}
                or (tag == "input" and element_type not in {"checkbox", "radio", "file", "submit", "button", "hidden"}))
    if action == "select":
        # 部分 UI 组件库把下拉触发器渲染为普通 button，展开后再生成 option/listbox。
        return tag in {"select", "button"} or role == "combobox"
    if action in {"check", "uncheck"}:
        return element_type in {"checkbox", "radio"} or role in {"checkbox", "radio"}
    if action == "click":
        return (tag in {"button", "a", "input", "select", "textarea"}
                or role in {"button", "link", "menuitem", "tab", "combobox", "textbox"}
                or bool(info.get("clickable")))
    return True


def _fingerprint(info):
    return "|".join(str(info.get(key) or "") for key in (
        "tag", "id", "name", "testId", "ariaLabel", "placeholder", "value", "text",
    ))


def _edit_distance(left, right):
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)
    previous = list(range(len(right) + 1))
    for row, left_char in enumerate(left, start=1):
        current = [row]
        for column, right_char in enumerate(right, start=1):
            current.append(min(
                current[-1] + 1,
                previous[column] + 1,
                previous[column - 1] + (left_char != right_char),
            ))
        previous = current
    return previous[-1]


def _fuzzy_score(target, actual):
    target, actual = normalize(target), normalize(actual)
    if len(target) < 4 or len(actual) < 4:
        return 0
    if target == actual:
        return 100
    distance = _edit_distance(target, actual)
    similarity = 1 - distance / max(len(target), len(actual))
    # 仅容许非常接近的拼写差异，例如 OpenAl / OpenAI；不能以模糊匹配猜测短词或不同元素。
    return round(55 + similarity * 40) if similarity >= 0.78 else 0


def _fuzzy_candidates(page, action, target):
    selector = CLICKABLE_SELECTOR if action == "click" else EDITABLE_SELECTOR if action in INPUT_ACTIONS | {"select", "check", "uncheck"} else ""
    if not selector or len(normalize(target)) < 4:
        return []
    try:
        elements = page.locator(selector)
        total = min(elements.count(), 120)
    except Exception:
        return []
    discovered = []
    for index in range(total):
        locator = elements.nth(index)
        try:
            if not locator.is_visible():
                continue
            info = _element_info(locator)
            candidates = [info.get("ariaLabel"), info.get("text"), info.get("placeholder"), info.get("name"), info.get("id")]
            score = max((_fuzzy_score(target, value) for value in candidates if value), default=0)
            if score:
                discovered.append(Candidate(locator, "fuzzy_accessible_name", score, target, detail={"fuzzy": True}))
        except Exception:
            continue
    return discovered


def _active_scope(page):
    """返回当前活动弹窗；没有可见弹窗时使用整个页面。

    多个弹窗同时存在时优先 z-index 更高的弹窗，层级相同则选择 DOM 中最后
    出现的弹窗（通常就是最后打开的弹窗）。
    """
    token = uuid.uuid4().hex
    try:
        selected = page.evaluate("""({token, selector}) => {
            const visible = element => {
                const style = getComputedStyle(element), box = element.getBoundingClientRect();
                return style.display !== 'none' && style.visibility !== 'hidden'
                    && Number(style.opacity || 1) !== 0 && box.width > 0 && box.height > 0;
            };
            const matches = [...document.querySelectorAll(selector)].filter(element =>
                element !== document.body && element !== document.documentElement && visible(element)
            );
            if (!matches.length) return '';

            // 一个弹窗组件经常同时在遮罩层、内容层和动画层使用 modal/dialog
            // 类名。只保留每组嵌套命中的最外层节点，避免把弹窗内部某个小区域
            // 误当成作用域，从而漏掉同弹窗里的其他输入框。
            const dialogs = matches.filter(element => !matches.some(parent =>
                parent !== element && parent.contains(element)
            ));
            const ranked = dialogs.map((element, order) => {
                let zIndex = 0, current = element;
                while (current && current !== document.documentElement) {
                    const value = Number.parseInt(getComputedStyle(current).zIndex, 10);
                    if (Number.isFinite(value)) zIndex = Math.max(zIndex, value);
                    current = current.parentElement;
                }
                const box = element.getBoundingClientRect();
                return {element, zIndex, order, area:box.width * box.height};
            }).sort((left, right) =>
                left.zIndex - right.zIndex || left.order - right.order || left.area - right.area
            );
            const active = ranked[ranked.length - 1].element;
            active.setAttribute('data-pw-smart-scope', token);
            return token;
        }""", {"token": token, "selector": DIALOG_SCOPE_SELECTOR})
    except Exception:
        selected = ""
    if selected:
        return page.locator(f'[data-pw-smart-scope="{selected}"]'), selected
    return page, ""


def _wait_for_active_scope(page, timeout, context_tokens):
    """关闭类操作等待异步弹窗挂载，避免提前误点登录通知等页面元素。"""
    scope, token = _active_scope(page)
    if token or not context_tokens:
        return scope, token
    deadline = time.monotonic() + min(max(timeout, 0) / 1000, 3)
    while time.monotonic() < deadline:
        page.wait_for_timeout(100)
        scope, token = _active_scope(page)
        if token:
            return scope, token
    return page, ""


def wait_for_dialog_state(page, visible, timeout=1500):
    """点击后等待弹窗出现或关闭，避免连续确认操作跨过 UI 状态切换。"""
    deadline = time.monotonic() + min(max(float(timeout), 0), 3000) / 1000
    while time.monotonic() < deadline:
        _scope, token = _active_scope(page)
        if bool(token) is bool(visible):
            return True
        page.wait_for_timeout(80)
    return False


def start_ui_transition_watch(page):
    """点击前安装轻量 DOM 观察器，供点击后统一等待页面交互状态稳定。"""
    token = uuid.uuid4().hex
    try:
        page.evaluate("""token => {
            const previous = window.__pwSmartTransitionWatch;
            if (previous?.observer) previous.observer.disconnect();
            const watch = {token, startedAt:performance.now(), lastMutation:performance.now(), mutations:0};
            watch.observer = new MutationObserver(() => {
                watch.lastMutation = performance.now();
                watch.mutations += 1;
            });
            watch.observer.observe(document.documentElement, {
                subtree:true, childList:true, attributes:true,
                attributeFilter:['class', 'style', 'hidden', 'open', 'aria-hidden', 'aria-expanded']
            });
            window.__pwSmartTransitionWatch = watch;
        }""", token)
    except Exception:
        return ""
    return token


def wait_for_ui_transition(page, token, timeout=1500):
    """等待点击引发的 DOM/动画变化安静下来，避免下一步抢跑。"""
    if not token:
        page.wait_for_timeout(120)
        return {"observed": False, "mutations": 0}
    try:
        return page.evaluate("""async ({token, timeout}) => {
            const started = performance.now(), minimum = Math.min(300, timeout), quietWindow = 140;
            while (performance.now() - started < timeout) {
                await new Promise(resolve => requestAnimationFrame(() => setTimeout(resolve, 40)));
                const watch = window.__pwSmartTransitionWatch;
                if (!watch || watch.token !== token) return {observed:false, mutations:0};
                const elapsed = performance.now() - started;
                if (elapsed >= minimum && performance.now() - watch.lastMutation >= quietWindow) {
                    watch.observer?.disconnect();
                    return {observed:watch.mutations > 0, mutations:watch.mutations};
                }
            }
            const watch = window.__pwSmartTransitionWatch;
            watch?.observer?.disconnect();
            return {observed:Boolean(watch?.mutations), mutations:Number(watch?.mutations || 0), timedOut:true};
        }""", {"token": token, "timeout": min(max(int(timeout), 120), 1500)})
    except Exception:
        page.wait_for_timeout(120)
        return {"observed": False, "mutations": 0}


ROW_COLUMN_SEMANTICS = (
    ("用户", "user"),
    ("邮箱", "电子邮箱", "邮箱地址", "email", "e-mail", "mail", "user"),
    ("用户名", "用户名称", "username", "user name"),
    ("操作", "actions", "action", "operation"),
    ("状态", "status", "state"),
    ("角色", "role"),
    ("余额", "balance"),
    ("创建时间", "created", "created at", "creation time"),
)


def _row_column_aliases(column):
    normalized = normalize(column)
    for aliases in ROW_COLUMN_SEMANTICS:
        if normalized and any(normalize(alias) == normalized for alias in aliases):
            return list(aliases)
    return [str(column or "")]


def _row_configuration(configuration):
    row = configuration.get("row", {}) if isinstance(configuration, dict) else {}
    if not isinstance(row, dict):
        return {}
    conditions = row.get("conditions", [])
    if not isinstance(conditions, list) or not conditions:
        return {}
    table = configuration.get("table", {})
    normalized_conditions = []
    for condition in conditions:
        item = dict(condition) if isinstance(condition, dict) else {}
        item["column_aliases"] = _row_column_aliases(item.get("column"))
        normalized_conditions.append(item)
    return {
        "conditions": normalized_conditions,
        "table_title": str(table.get("title") or "").strip() if isinstance(table, dict) else "",
    }


def _find_row_scope(page, parent_scope_token, row_configuration, timeout):
    """在当前页面/弹窗中按列条件找到唯一数据行。

    支持原生 table 与 ARIA table/grid。每轮只执行一次 DOM 遍历，找不到时
    才推进滚动容器，用于虚拟表格和延迟加载。
    """
    row_token = uuid.uuid4().hex
    deadline = time.monotonic() + timeout / 1000
    last_result = {"count": 0, "rows": [], "missingColumns": []}
    while time.monotonic() < deadline:
        last_result = page.evaluate("""({parentScopeToken, rowToken, configuration}) => {
            const compact = value => String(value || '').normalize('NFKC').trim().toLowerCase()
                .replace(/[\\s_\\-:/：()（）,.\uff0c。]+/g, '');
            const visible = element => {
                const style = getComputedStyle(element), box = element.getBoundingClientRect();
                return style.display !== 'none' && style.visibility !== 'hidden'
                    && Number(style.opacity || 1) !== 0 && box.width > 0 && box.height > 0;
            };
            const matches = (actual, operator, expected) => {
                const candidates = Array.isArray(actual) ? actual : [actual];
                const right = String(expected ?? '').normalize('NFKC').trim();
                const one = value => {
                    const left = String(value || '').normalize('NFKC').trim();
                    if (operator === 'contains') return compact(left).includes(compact(right));
                    if (operator === 'starts_with') return compact(left).startsWith(compact(right));
                    if (operator === 'regex') {
                        try { return new RegExp(right).test(left); } catch (_) { return false; }
                    }
                    return compact(left) === compact(right);
                };
                if (operator === 'not_equals') return candidates.every(value => !one(value));
                return candidates.some(one);
            };
            // 弹窗提交后通常会先触发异步请求，再关闭弹窗并刷新页面表格。
            // 行定位开始时可能拿到旧弹窗 token；该弹窗一旦被移除或隐藏，必须
            // 自动回到 document 重新找表格，不能在失效作用域里一直等到超时。
            const scopedRoot = parentScopeToken
                ? document.querySelector(`[data-pw-smart-scope="${parentScopeToken}"]`)
                : null;
            const root = scopedRoot && visible(scopedRoot) ? scopedRoot : document;
            const tableTitle = compact(configuration.table_title);
            let containers = [...root.querySelectorAll('table, [role="table"], [role="grid"]')].filter(visible);
            if (!containers.length) containers = [root];
            const matched = [], missingColumns = new Set();
            for (const container of containers) {
                if (tableTitle) {
                    const ownName = compact([
                        container.getAttribute?.('aria-label'), container.querySelector?.('caption')?.innerText,
                        container.previousElementSibling?.innerText
                    ].filter(Boolean).join(' '));
                    if (!ownName.includes(tableTitle)) continue;
                }
                const headerNodes = [...container.querySelectorAll('thead th, [role="columnheader"]')].filter(visible);
                const headers = headerNodes.map(node => compact(node.innerText || node.getAttribute('aria-label')));
                let rows = [...container.querySelectorAll('tbody tr, [role="row"]')].filter(visible);
                rows = rows.filter(row => !row.matches('[role="rowheader"]')
                    && !row.querySelector('[role="columnheader"]') && !row.closest('thead'));
                for (const row of rows) {
                    const cells = [...row.querySelectorAll(':scope > td, :scope > th, :scope > [role="cell"], :scope > [role="gridcell"]')];
                    if (!cells.length) continue;
                    const values = cells.map(cell => (cell.innerText || cell.textContent || '').trim());
                    const variants = cells.map((cell, index) => [
                        values[index],
                        ...[...cell.querySelectorAll('*')]
                            .filter(node => !node.children.length && (node.innerText || '').trim())
                            .map(node => (node.innerText || '').trim())
                    ]);
                    let accepted = true;
                    for (const condition of configuration.conditions) {
                        const column = compact(condition.column);
                        const columnAliases = (condition.column_aliases || [condition.column]).map(compact).filter(Boolean);
                        let columnIndex = -1;
                        for (const alias of columnAliases) {
                            columnIndex = headers.findIndex(header =>
                                header && (header === alias || header.includes(alias) || alias.includes(header))
                            );
                            if (columnIndex >= 0) break;
                        }
                        if (column && columnIndex < 0) {
                            missingColumns.add(String(condition.column || ''));
                            accepted = false;
                            break;
                        }
                        const actual = column ? variants[columnIndex] : [values.join(' ')];
                        if (!matches(actual, condition.operator || 'equals', condition.value)) {
                            accepted = false;
                            break;
                        }
                    }
                    if (accepted) matched.push({row, summary:values.slice(0, 8).join(' | ').slice(0, 300)});
                }
            }
            if (matched.length === 1) matched[0].row.setAttribute('data-pw-smart-scope', rowToken);
            return {count:matched.length, rows:matched.slice(0,5).map(item => item.summary), missingColumns:[...missingColumns]};
        }""", {
            "parentScopeToken": parent_scope_token,
            "rowToken": row_token,
            "configuration": row_configuration,
        })
        if last_result.get("count") == 1:
            return page.locator(f'[data-pw-smart-scope="{row_token}"]'), row_token, {
                "conditions": row_configuration["conditions"],
                "table_title": row_configuration.get("table_title", ""),
                "row_summary": (last_result.get("rows") or [""])[0],
            }
        if last_result.get("count", 0) > 1:
            raise SmartLocatorError(
                f"数据行条件匹配到 {last_result['count']} 行，请增加列条件直到唯一。"
                f"候选行：{last_result.get('rows') or []}"
            )
        _scroll_search_regions(page, parent_scope_token)
        page.wait_for_timeout(150)
    if last_result.get("missingColumns"):
        raise SmartLocatorError(
            f"数据行定位失败：当前表格中未找到列 {last_result['missingColumns']}。"
        )
    conditions = ", ".join(
        f"{item.get('column') or '整行'} {item.get('operator') or 'equals'} {item.get('value', '')}"
        for item in row_configuration["conditions"]
    )
    raise SmartLocatorError(f"未找到满足条件的数据行：{conditions}。")


def _scroll_search_regions(page, scope_token=""):
    """推进页面与弹窗的可滚动容器，覆盖延迟/虚拟渲染的字段。

    不根据固定 CSS 类名猜测业务页面：只滚动当前实际可滚动的容器，优先弹窗、
    抽屉等最内层区域。每轮只推进约 70% 视区，避免一次跳过可见内容。
    """
    try:
        return page.evaluate("""scopeToken => {
            const root = scopeToken
              ? document.querySelector(`[data-pw-smart-scope="${scopeToken}"]`)
              : document;
            if (!root) return false;
            const regions = root === document
              ? [...document.querySelectorAll('*')]
              : [root, ...root.querySelectorAll('*')]
              .filter(node => {
                const style = getComputedStyle(node);
                return node.scrollHeight > node.clientHeight + 8
                  && /(auto|scroll)/.test(style.overflowY)
                  && style.visibility !== 'hidden';
              })
              .sort((left, right) => {
                const leftModal = left.closest('[role="dialog"], dialog, [aria-modal="true"]') ? 1 : 0;
                const rightModal = right.closest('[role="dialog"], dialog, [aria-modal="true"]') ? 1 : 0;
                return rightModal - leftModal || right.clientHeight - left.clientHeight;
              });
            let moved = false;
            for (const region of regions) {
                const before = region.scrollTop;
                const bottom = region.scrollHeight - region.clientHeight;
                // 到达底部后回到顶部继续扫描，支持目标位于当前滚动位置上方的场景。
                const next = before >= bottom - 2
                  ? 0
                  : Math.min(before + Math.max(180, region.clientHeight * 0.7), bottom);
                region.scrollTop = next;
                moved = moved || next !== before;
            }
            if (!regions.length && !scopeToken) {
                const before = window.scrollY;
                window.scrollBy(0, Math.max(180, window.innerHeight * 0.7));
                moved = window.scrollY > before;
            }
            return moved;
        }""", scope_token)
    except Exception:
        return False


def _summaries(items):
    return [{
        "strategy": item["strategy"], "score": item["score"], "element": item["info"],
    } for item in items]


def _context_bonus(info, context_tokens):
    """优先操作当前弹层内、且具备更明确可访问上下文的元素。"""
    bonus = 18 if info.get("inDialog") else 0
    accessible_name = normalize(f"{info.get('ariaLabel', '')} {info.get('text', '')}")
    if context_tokens and any(normalize(token) in accessible_name for token in context_tokens):
        bonus += 20
    return bonus


def _exact_candidates(page, action, target, configuration):
    """只构造零歧义的精确语义策略；命中后无需建立 DOM 索引。"""
    candidates = []
    phrase = str(target or "").strip()
    test_id = str(configuration.get("test_id") or "").strip()
    role = str(configuration.get("role") or "").strip()
    if test_id:
        _add(candidates, page.get_by_test_id(test_id), "test_id", 100, test_id)
    if not phrase:
        return candidates
    if action in INPUT_ACTIONS | TEXT_ACTIONS | {"select", "check", "uncheck"}:
        _add(candidates, page.get_by_label(phrase, exact=True), "label", 95, phrase)
        _add(candidates, page.get_by_placeholder(phrase, exact=True), "placeholder", 88, phrase)
        _add(candidates, page.get_by_role("textbox", name=phrase, exact=True), "role_textbox", 92, phrase)
        _add(candidates, page.locator(f'[aria-label="{phrase}"]'), "aria_label", 90, phrase)
        _add(candidates, page.locator(f'[name="{phrase}"]'), "name", 82, phrase)
        _add(candidates, page.locator(f'[id="{phrase}"]'), "id", 82, phrase)
        if action == "select":
            _add(candidates, page.get_by_role("button", name=phrase, exact=True), "role_button", 95, phrase)
            _add(candidates, page.get_by_role("combobox", name=phrase, exact=True), "role_combobox", 95, phrase)
            _add(candidates, page.get_by_text(phrase, exact=True).locator(
                "xpath=ancestor-or-self::*[self::button or self::select or @role='button' or @role='combobox'][1]"
            ), "text_select_trigger", 88, phrase)
    if action in {"click", "assert_visible", "assert_text"}:
        if action == "click":
            # 原生 input[type=button|submit] 的可见按钮文案来自 value 而不是 innerText。
            # 若不纳入该策略，页面上虽能看到“生成并复制”，但不会进入文本候选集。
            value_literal = _xpath_literal(phrase)
            _add(candidates, page.locator(
                "xpath=//input[(@type='button' or @type='submit' or @type='reset' or @type='image') "
                f"and @value={value_literal}]"
            ), "input_value_button", 96, phrase)
            _add(candidates, page.locator(
                f"xpath=//button[@value={value_literal} or @role='button' and @value={value_literal}]"
            ), "button_value", 94, phrase)
            _add(candidates, page.locator(
                f"xpath=//*[@onclick and normalize-space(string(.))={value_literal}]"
            ), "onclick_text", 96, phrase)
        _add(candidates, page.get_by_text(phrase, exact=True).locator(
            "xpath=ancestor-or-self::*[self::button or self::a or @role='button' or @role='link'][1]"
        ), "text_clickable_ancestor", 98, phrase)
        _add(candidates, page.get_by_role("link", name=phrase, exact=True), "role_link", 94, phrase)
        _add(candidates, page.get_by_role("button", name=phrase, exact=True), "role_button", 92, phrase)
    if role:
        _add(candidates, page.get_by_role(role, name=phrase, exact=True), "configured_role", 96, phrase)
    return candidates


def _collect_ranked(candidates, action, fingerprint, context_tokens):
    seen = {}
    for candidate in candidates:
        try:
            count = min(candidate.locator.count(), 50)
        except Exception:
            continue
        for index in range(count):
            concrete = candidate.locator.nth(index)
            try:
                info = _element_info(concrete)
                if not info.get("visible") or info.get("disabled") or not _compatible(action, info):
                    continue
                key = _fingerprint(info)
                score = candidate.score + 15 + similarity(fingerprint, info) + _context_bonus(info, context_tokens)
                current = seen.get(key)
                if current is None or score > current["score"]:
                    seen[key] = {
                        "locator": concrete, "strategy": candidate.strategy,
                        "score": score, "info": info, "phrase": candidate.phrase,
                    }
            except Exception:
                continue
    return sorted(seen.values(), key=lambda item: item["score"], reverse=True)


def _first_unique_exact(candidates, action, fingerprint, context_tokens):
    """按可靠性顺序检查精确策略，唯一有效命中后立即停止。"""
    for candidate in candidates:
        try:
            if candidate.locator.count() != 1:
                continue
            locator = candidate.locator.first
            info = _element_info(locator)
            if not info.get("visible") or info.get("disabled") or not _compatible(action, info):
                continue
            return {
                "locator": locator,
                "strategy": candidate.strategy,
                "score": candidate.score + 15 + similarity(fingerprint, info)
                         + _context_bonus(info, context_tokens),
                "info": info,
                "phrase": candidate.phrase,
            }
        except Exception:
            continue
    return None


def _reusable_locator(info):
    """从成功元素生成跨运行可复用的强定位表达式。"""
    if info.get("testId"):
        return {"type": "test_id", "value": info["testId"]}
    if info.get("id"):
        return {"type": "id", "value": info["id"]}
    if info.get("name"):
        return {"type": "name", "value": info["name"], "tag": info.get("tag", "")}
    if info.get("ariaLabel"):
        return {"type": "aria_label", "value": info["ariaLabel"]}
    if info.get("placeholder"):
        return {"type": "placeholder", "value": info["placeholder"]}
    if info.get("value") and info.get("tag") in {"button", "input"}:
        return {"type": "control_value", "value": info["value"], "tag": info.get("tag", "")}
    role = info.get("role") or ({"button": "button", "a": "link", "select": "combobox"}.get(info.get("tag")))
    if role and info.get("text"):
        return {"type": "role", "value": info["text"], "role": role, "tag": info.get("tag", "")}
    return None


def _locator_from_spec(page, spec):
    locator_type, value = str(spec.get("type") or ""), str(spec.get("value") or "")
    if not locator_type or not value:
        return None
    if locator_type == "test_id":
        return page.get_by_test_id(value)
    if locator_type == "id":
        return page.locator(f"xpath=//*[@id={_xpath_literal(value)}]")
    if locator_type == "name":
        tag = str(spec.get("tag") or "*")
        return page.locator(f"xpath=//{tag}[@name={_xpath_literal(value)}]")
    if locator_type == "aria_label":
        return page.locator(f"xpath=//*[@aria-label={_xpath_literal(value)}]")
    if locator_type == "placeholder":
        return page.get_by_placeholder(value, exact=True)
    if locator_type == "control_value":
        tag = str(spec.get("tag") or "*")
        return page.locator(f"xpath=//{tag}[@value={_xpath_literal(value)}]")
    if locator_type == "role":
        role = str(spec.get("role") or "button")
        tag = str(spec.get("tag") or {"button": "button", "link": "a", "combobox": "select"}.get(role) or "*")
        normalized_text = " ".join(value.split())
        # 自定义 combobox 的可访问名称不一定来自 innerText，因此不能只依赖 get_by_role(name=)。
        return page.locator(
            f"xpath=//*[((@role={_xpath_literal(role)}) or (not(@role) and self::{tag})) "
            f"and normalize-space(string(.))={_xpath_literal(normalized_text)}]"
        )
    return None


def _xpath_literal(value):
    if "'" not in value:
        return f"'{value}'"
    if '"' not in value:
        return f'"{value}"'
    parts = value.split("'")
    return "concat(" + ", \"'\", ".join(f"'{part}'" for part in parts) + ")"


def _try_reusable(page, action, fingerprint, context_tokens):
    spec = (fingerprint or {}).get("_locator")
    if not isinstance(spec, dict):
        return None
    try:
        locator = _locator_from_spec(page, spec)
        if locator is None:
            return None
        if locator.count() != 1:
            return None
        locator = locator.first
        info = _element_info(locator)
        fingerprint_score = similarity(fingerprint, info)
        if info.get("visible") and not info.get("disabled") and _compatible(action, info) and fingerprint_score >= 12:
            return {
                "locator": locator,
                "strategy": "learned_locator",
                "score": 125 + fingerprint_score + _context_bonus(info, context_tokens),
                "info": info,
                "phrase": str(spec.get("value") or ""),
            }
    except Exception:
        return None
    return None


def _index_selector(action):
    if action in INPUT_ACTIONS | {"select", "check", "uncheck"}:
        return FORM_CONTROL_SELECTOR
    if action == "click":
        return f"{CLICKABLE_SELECTOR}, select, textarea, [role='combobox'], [aria-label], [data-testid]"
    return "button, a, input, textarea, select, [role], [aria-label], [data-testid], label, p, span, div, h1, h2, h3, h4, td, th"


def _build_dom_index(page, action, scope_token=""):
    """一次浏览器调用构建可操作元素索引，避免 Python/浏览器逐元素往返。"""
    token = uuid.uuid4().hex
    return page.evaluate("""({selector, token, scopeToken, preferLeafText}) => {
        const root = scopeToken
          ? document.querySelector(`[data-pw-smart-scope="${scopeToken}"]`)
          : document;
        if (!root) return [];
        const compact = value => String(value || '').normalize('NFKC').trim().toLowerCase()
          .replace(/[\\s_\\-:/：()（）,.，。]+/g, '');
        const visible = element => {
          const style = getComputedStyle(element), box = element.getBoundingClientRect();
          return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity || 1) !== 0
            && box.width > 0 && box.height > 0;
        };
        const labels = [...root.querySelectorAll('label, span, div, p, dt, strong, b')]
          .filter(visible)
          .map(element => ({element, text:(element.innerText || '').trim().slice(0, 120), box:element.getBoundingClientRect()}))
          .filter(item => item.text && item.text.length <= 120);
        const indexedElements = [...root.querySelectorAll(selector)].filter(visible).filter(element => {
          if (!preferLeafText) return true;
          const ownText = compact(element.innerText || element.textContent || '');
          if (!ownText) return true;
          // 提示、Toast 等组件经常由多层 div 包裹，每一层 innerText 都完全相同。
          // 断言场景只保留最内层的同文本节点；不同位置的独立提示仍会保留，继续
          // 交给唯一性保护处理，避免为了通过断言而随意选择其中一个。
          return ![...element.querySelectorAll(selector)].some(descendant =>
            visible(descendant)
            && compact(descendant.innerText || descendant.textContent || '') === ownText
          );
        });
        return indexedElements.slice(0, 500).map((element, index) => {
          element.setAttribute('data-pw-smart-index', `${token}-${index}`);
          const box = element.getBoundingClientRect();
          const nearbyLabels = labels.map(label => {
            const vertical = box.top - label.box.bottom;
            const horizontal = Math.max(0, Math.max(label.box.left, box.left) - Math.min(label.box.right, box.right));
            return {text:label.text, vertical, horizontalGap:horizontal,
              distance:Math.abs(vertical) + horizontal * .35,
              valid:vertical >= -36 && vertical <= 220 && horizontal <= 220};
          }).filter(item => item.valid).sort((a,b) => a.distance-b.distance).slice(0, 3);
          return {
            index:`${token}-${index}`, tag:element.tagName.toLowerCase(),
            type:(element.getAttribute('type') || '').toLowerCase(), role:element.getAttribute('role') || '',
            id:element.id || '', name:element.getAttribute('name') || '',
            testId:element.getAttribute('data-testid') || '', ariaLabel:element.getAttribute('aria-label') || '',
            text:(element.innerText || '').trim().slice(0,120),
            value:(element.getAttribute('value') || '').trim().slice(0,120),
            placeholder:element.getAttribute('placeholder') || '',
            clickable:!!element.getAttribute('onclick') || element.tabIndex >= 0
              || ['button', 'a'].includes(element.tagName.toLowerCase())
              || ['button', 'link', 'tab', 'menuitem'].includes(element.getAttribute('role') || ''),
            disabled:!!element.disabled, editable:!!element.isContentEditable,
            x:box.x, y:box.y,
            inDialog:!!element.closest('[role="dialog"], dialog, [aria-modal="true"]'),
            dialogLabel:(element.closest('[role="dialog"], dialog, [aria-modal="true"]')?.getAttribute('aria-label') || ''),
            nearbyLabels
          };
        });
    }""", {
        "selector": _index_selector(action), "token": token, "scopeToken": scope_token,
        "preferLeafText": action in TEXT_ACTIONS,
    })


def _score_index(page, index, action, target, configuration, fingerprint, context_tokens):
    phrases, input_types = semantic_terms(target, configuration)
    exact_target = normalize(target)
    ranked = []
    for info in index or []:
        if info.get("disabled") or not _compatible(action, info):
            continue
        best_score, best_strategy, best_phrase = 0, "", target
        values = {
            "test_id": info.get("testId", ""), "aria_label": info.get("ariaLabel", ""),
            "placeholder": info.get("placeholder", ""), "name": info.get("name", ""),
            "id": info.get("id", ""), "text": info.get("text", ""),
        }
        # value 是原生按钮/提交控件的可见名称，不将普通输入框已有值视为定位依据。
        if action == "click" and info.get("tag") in {"button", "input"}:
            values["control_value"] = info.get("value", "")
        for phrase in phrases:
            wanted = normalize(phrase)
            if not wanted:
                continue
            semantic_penalty = 12 if wanted != exact_target else 0
            for strategy, value in values.items():
                actual = normalize(value)
                if not actual:
                    continue
                if actual == wanted:
                    base = {"test_id": 100, "aria_label": 90, "placeholder": 88, "name": 82, "id": 82, "text": 86, "control_value": 94}[strategy]
                elif wanted in actual:
                    base = {"test_id": 86, "aria_label": 82, "placeholder": 80, "name": 74, "id": 74, "text": 62, "control_value": 82}[strategy]
                else:
                    base = 0
                score = base - semantic_penalty
                if score > best_score:
                    best_score, best_strategy, best_phrase = score, f"indexed_{strategy}", phrase
            # 空间标签只用于表单控件操作；点击和文本断言必须匹配元素自身，不能把
            # Toast 文本下方的大块 div 误判为“标签对应输入框”。
            if action in INPUT_ACTIONS | {"select", "check", "uncheck"}:
                nearby_labels = info.get("nearbyLabels") or []
                for label_index, label in enumerate(nearby_labels):
                    if normalize(label.get("text")) == wanted:
                        distance = float(label.get("distance") or 0)
                        vertical = label.get("vertical")
                        horizontal_gap = float(label.get("horizontalGap") or 0)
                        # 最近标签且紧邻控件是明确的字段归属；更远的同名文字只能作为弱提示。
                        # 例如 textarea 上方能看到“标题”，但它最近的标签其实是“内容”。
                        if (label_index == 0 and vertical is not None
                                and 0 <= float(vertical) <= 32 and horizontal_gap <= 24):
                            score = 105 - semantic_penalty
                            strategy = "indexed_label_below"
                        elif label_index == 0 and distance <= 24:
                            score = 90 - semantic_penalty
                            strategy = "indexed_nearby_field"
                        else:
                            score = max(45, round(55 - min(distance, 180) / 9)) - semantic_penalty
                            strategy = "indexed_nearby_field"
                        if score > best_score:
                            best_score, best_strategy, best_phrase = score, strategy, phrase
        if not best_score and info.get("type") in input_types:
            best_score, best_strategy, best_phrase = 58, "indexed_semantic_type", info.get("type")
        if not best_score:
            actual_values = [value for value in values.values() if value]
            fuzzy = max((_fuzzy_score(target, value) for value in actual_values), default=0)
            if fuzzy:
                best_score, best_strategy = fuzzy, "indexed_fuzzy"
        if not best_score:
            continue
        score = best_score + 15 + similarity(fingerprint, info) + _context_bonus(info, context_tokens)
        ranked.append({
            "locator": page.locator(f'[data-pw-smart-index="{info["index"]}"]'),
            "strategy": best_strategy, "score": score, "info": info, "phrase": best_phrase,
        })
    return sorted(ranked, key=lambda item: item["score"], reverse=True)


def _is_ambiguous(ranked):
    if not ranked:
        return False
    best, second = ranked[0], ranked[1] if len(ranked) > 1 else None
    second_is_competitive = bool(second) and not (
        best["strategy"] not in FALLBACK_STRATEGIES and second["strategy"] in FALLBACK_STRATEGIES
    )
    return best["score"] < 70 or bool(second_is_competitive and best["score"] - second["score"] < 15)


def _prefer_creation_action(ranked, target):
    """同文案的创建入口视为等价操作，优先页面顶部工具栏入口。

    仅对创建类明确意图生效；表格里的“更多/编辑/删除”等重复操作仍必须通过
    数据行条件消歧，避免误操作其他记录。
    """
    wanted = normalize(target)
    creation_intent = any(token in wanted for token in ("创建", "新增", "添加", "create", "new", "add"))
    if not creation_intent or len(ranked) < 2:
        return None
    competitive = [item for item in ranked if ranked[0]["score"] - item["score"] < 15]
    if len(competitive) < 2:
        return None
    if not all(
        item["info"].get("tag") == "button" and normalize(item["info"].get("text")) == wanted
        for item in competitive
    ):
        return None
    # 工具栏主操作通常位于页面更上方；同一水平线上再优先右侧。
    return min(
        competitive,
        key=lambda item: (float(item["info"].get("y") or 0), -float(item["info"].get("x") or 0)),
    )


def _resolution(best, ranked, fingerprint, stage, started_at):
    reusable = _reusable_locator(best["info"])
    return {
        "strategy": best["strategy"], "confidence": best["score"],
        "matched_phrase": best["phrase"], "fingerprint_match": similarity(fingerprint, best["info"]),
        "element": best["info"], "candidates": _summaries(ranked[:5]),
        "stage": stage, "locator_duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
        **({"reusable_locator": reusable} if reusable else {}),
    }


def resolve(page, step, timeout, fingerprint=None):
    """解析自动定位元素，返回 ``(locator, resolution)``。"""
    started_at = time.perf_counter()
    action = str(getattr(step, "action", ""))
    target = str(getattr(step, "target", "") or "").strip()
    configuration = _config(step)
    context_tokens = semantic_context_tokens(target, configuration)
    scope, scope_token = _wait_for_active_scope(page, timeout, context_tokens)
    row_detail = None
    row_configuration = _row_configuration(configuration)
    if row_configuration:
        scope, scope_token, row_detail = _find_row_scope(page, scope_token, row_configuration, timeout)
    # 当前页面存在可见文字精确命中时优先尊重本次描述，避免历史指纹把“公告”
    # 继续定位到曾经误学到的顶部通知铃铛。
    best = _first_unique_exact(
        _exact_candidates(scope, action, target, configuration), action, fingerprint, context_tokens,
    )
    if best:
        ranked = [best]
        try:
            best["locator"].scroll_into_view_if_needed(timeout=min(max(timeout, 500), 3000))
        except Exception:
            pass
        resolution = _resolution(best, ranked, fingerprint, "exact", started_at)
        if row_detail:
            resolution["row_scope"] = row_detail
        return best["locator"], resolution

    learned = _try_reusable(scope, action, fingerprint, context_tokens)
    if learned:
        ranked = [learned]
        best = learned
        try:
            best["locator"].scroll_into_view_if_needed(timeout=min(max(timeout, 500), 3000))
        except Exception:
            pass
        resolution = _resolution(best, ranked, fingerprint, "learned", started_at)
        if row_detail:
            resolution["row_scope"] = row_detail
        return best["locator"], resolution

    deadline = time.monotonic() + timeout / 1000
    ranked = []
    while time.monotonic() < deadline:
        # 每轮只做一次浏览器 DOM 读取；滚动/懒加载后才重建索引。
        index = _build_dom_index(page, action, scope_token)
        ranked = _score_index(page, index, action, target, configuration, fingerprint, context_tokens)
        if ranked:
            break
        _scroll_search_regions(page, scope_token)
        page.wait_for_timeout(150)

    if not ranked:
        raise SmartLocatorError(
            f"未找到与“{target}”匹配且可操作的元素。可补充更具体的描述或配置手动兜底表达式。"
        )
    best = ranked[0]
    creation_action = _prefer_creation_action(ranked, target)
    if creation_action:
        best = creation_action
    elif _is_ambiguous(ranked):
        details = _summaries(ranked[:5])
        raise SmartLocatorError(
            f"无法唯一定位“{target}”：最高候选 {best['strategy']}（{best['score']} 分），"
            f"请补充元素描述、角色或手动兜底表达式。候选：{details}",
            details,
        )
    # 显式滚入视区：既让后续操作稳定，也使运行截图/有头浏览器能看到当前目标。
    try:
        best["locator"].scroll_into_view_if_needed(timeout=min(max(timeout, 500), 3000))
    except Exception:
        pass
    resolution = _resolution(best, ranked, fingerprint, "dom_index", started_at)
    if row_detail:
        resolution["row_scope"] = row_detail
    return best["locator"], resolution
