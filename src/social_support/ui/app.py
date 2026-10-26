"""Streamlit UI. Run with: ``uv run streamlit run src/social_support/ui/app.py``"""

import streamlit as st

from social_support.ui.client import ApiClient, ApiError

EMPLOYMENT_STATUSES = {
    "EMPLOYED": "Employed",
    "SELF_EMPLOYED": "Self-employed",
    "UNEMPLOYED": "Unemployed",
    "STUDENT": "Student",
    "RETIRED": "Retired",
}
OUTCOMES = {  # label, badge colour
    "APPROVE": ("Approve", "green"),
    "NEEDS_HUMAN_REVIEW": ("Needs Human Review", "orange"),
    "SOFT_DECLINE": ("Soft Decline", "gray"),
}
OUTCOME_HEADLINES = {
    "APPROVE": "Your application meets the criteria for financial support.",
    "SOFT_DECLINE": "Your application does not meet the criteria at this time.",
    "NEEDS_HUMAN_REVIEW": "A caseworker will review your application.",
}
FINDING_ICONS = {"APPROVE": "✅", "SOFT_DECLINE": "❌", "NEEDS_HUMAN_REVIEW": "⚠️"}
INCOME_HELP = (
    "Net (take-home) monthly income from all sources (salary, business, rental, pensions, "
    "existing benefits) for all household members"
)
# Feature 004: the five mandatory documents, as (upload field, label, accepted types).
DOCUMENTS = (
    ("bank_statement", "Bank statement (PDF)", ["pdf"]),
    ("emirates_id_card", "Emirates ID card (image)", ["png", "jpg", "jpeg"]),
    ("resume", "Resume (PDF)", ["pdf"]),
    ("assets_liabilities", "Assets and liabilities (Excel)", ["xlsx"]),
    ("credit_report", "Credit report (PDF)", ["pdf"]),
)
CHECK_LABELS = {
    "name_vs_id_card": "Name matches the Emirates ID card",
    "emirates_id_vs_id_card": "Emirates ID number matches the card",
    "name_vs_bank_holder": "Name matches the bank account holder",
    "income_vs_bank": "Declared income matches the bank statement",
}
CHECK_MARKS = {True: "✅ Passed", False: "❌ Failed", None: "– Not checked"}


@st.cache_resource
def get_client() -> ApiClient:
    return ApiClient()


def _submit_application() -> None:
    state = st.session_state
    payload = {
        "full_name": state.full_name,
        "emirates_id": state.emirates_id,
        "family_size": int(state.family_size),
        "net_monthly_income_aed": f"{state.net_monthly_income_aed:.2f}",
        "employment_status": state.employment_status,
    }
    # Missing documents are left out: the API names each one (FR-002).
    files = {}
    for field, _label, _types in DOCUMENTS:
        upload = state.get(f"upload_{field}")
        if upload is not None:
            files[field] = (upload.name, upload.getvalue(), upload.type)
    state.apply_result, state.apply_errors, state.apply_failure = None, {}, None
    state.enablement, state.enablement_failure = None, None
    try:
        state.apply_result = get_client().submit_with_documents(payload, files)
        state.apply_emirates_id = state.emirates_id
    except ApiError as exc:
        if exc.field_errors:
            state.apply_errors = exc.field_errors
        else:
            state.apply_failure = exc.detail


def _request_submit() -> None:
    """Form callback: the slow submission runs in the script body, under a spinner."""
    st.session_state.submit_pending = True


def _field_error(field: str) -> None:
    message = st.session_state.get("apply_errors", {}).get(field)
    if message:
        st.markdown(f":red[{message}]")


def _lookup_application() -> None:
    state = st.session_state
    state.lookup_result, state.lookup_failure = None, None
    try:
        state.lookup_result = get_client().lookup(state.lookup_reference, state.lookup_emirates_id)
    except ApiError as exc:
        state.lookup_failure = exc.detail


def _show_findings(findings: list[dict]) -> None:
    st.markdown("**Why**")
    for finding in findings:
        icon = FINDING_ICONS[finding["outcome"]]
        source = ", ".join(finding["sources"])
        line = f"{icon} {finding['text']}"
        st.markdown(f"{line}  \n:gray[Source: {source}]" if source else line)


def _show_decision(result: dict, *, show_reference_hint: bool = True) -> None:
    decision = result["decision"]
    label, colour = OUTCOMES[decision["outcome"]]
    st.subheader("Recommendation")
    st.badge(label, color=colour)
    findings = decision.get("findings") or []
    if findings:
        st.markdown(OUTCOME_HEADLINES[decision["outcome"]])
        _show_findings(findings)
    else:
        st.markdown(decision["explanation"])
    if decision["suggested_next_steps"]:
        st.markdown("**Suggested next steps**")
        st.markdown("\n".join(f"- {step}" for step in decision["suggested_next_steps"]))
    if show_reference_hint:
        st.markdown(
            f"Reference number: **{result['reference_number']}**. Keep it to look up this "
            "application later."
        )
    if result["previous_application_exists"]:
        st.info("A previous application exists for this Emirates ID.")


def _pretty(name: str) -> str:
    text = name.removesuffix("_aed").replace("_", " ").capitalize()
    return f"{text} (AED)" if name.endswith("_aed") else text


def _show_checks_and_documents(result: dict) -> None:
    checks = result.get("cross_checks") or []
    if checks:
        st.markdown("**Cross-document checks**")
        st.table(
            [
                {
                    "Check": CHECK_LABELS.get(c["check_id"], c["check_id"]),
                    "Result": CHECK_MARKS[c["passed"]],
                    "Form": c["form_value"],
                    "Document": c["document_value"],
                }
                for c in checks
            ]
        )
    documents = result.get("documents") or []
    if documents:
        st.markdown("**What we read from your documents**")
    for document in documents:
        mark = "✅" if document["ok"] else "❌"
        with st.expander(f"{mark} {document['label']}"):
            if document["error"]:
                st.error(f"Could not be read: {document['error']}")
            rows = [{"Field": _pretty(k), "Value": v} for k, v in document["fields"].items()]
            rows += [
                {"Field": _pretty(k), "Value": ", ".join(v)}
                for k, v in document["items"].items()
                if v
            ]
            if rows:
                st.table(rows)


def _show_enablement(result: dict) -> None:
    """US4: the plan comes from the local LLM after the decision is already on screen."""
    state = st.session_state
    st.subheader("Economic enablement plan")
    if state.get("enablement") is None and state.get("enablement_failure") is None:
        with st.spinner("Preparing your economic enablement plan with the local AI model…"):
            try:
                state.enablement = get_client().enablement(
                    result["reference_number"], state.get("apply_emirates_id", "")
                )
            except ApiError as exc:
                state.enablement_failure = exc.detail
    if state.get("enablement_failure"):
        st.warning(f"The enablement plan is not available: {state.enablement_failure}")
        return
    plan = state.enablement
    if plan["is_fallback"]:
        st.caption("General guidance (the local AI model was unavailable).")
    else:
        st.caption(f"Personalised by the local model {plan['model']} from your resume and profile.")
    st.markdown("**Training and upskilling**")
    st.markdown("\n".join(f"- {item}" for item in plan["training"]))
    st.markdown("**Job matches**")
    st.markdown("\n".join(f"- {item}" for item in plan["job_matches"]))
    st.markdown("**Career counselling**")
    st.markdown(plan["career_counselling"])


def render_apply(client: ApiClient) -> None:
    st.caption("Use synthetic data only. Do not enter real personal information.")
    with st.form("apply"):
        st.text_input("Full name", key="full_name")
        _field_error("full_name")
        st.text_input("Emirates ID", key="emirates_id", placeholder="784-YYYY-NNNNNNN-N")
        _field_error("emirates_id")
        st.number_input("Family size (including the applicant)", key="family_size", value=1, step=1)
        _field_error("family_size")
        st.number_input(
            "Net monthly household income (AED)",
            key="net_monthly_income_aed",
            value=0.0,
            step=100.0,
            format="%.2f",
            help=INCOME_HELP,
        )
        st.caption(f"{INCOME_HELP}.")  # FR-001: visible, not only on hover
        _field_error("net_monthly_income_aed")
        st.selectbox(
            "Employment status",
            options=list(EMPLOYMENT_STATUSES),
            format_func=EMPLOYMENT_STATUSES.get,
            key="employment_status",
        )
        _field_error("employment_status")
        st.markdown("**Documents** (all five are required)")
        for field, label, types in DOCUMENTS:
            st.file_uploader(label, type=types, key=f"upload_{field}")
            _field_error(field)
        st.form_submit_button("Submit application", on_click=_request_submit)

    if st.session_state.get("submit_pending"):
        st.session_state.submit_pending = False
        with st.spinner("Reading your documents and assessing your application…"):
            _submit_application()
        st.rerun()  # so field errors render inside the form above
    if st.session_state.get("apply_failure"):
        st.error(st.session_state.apply_failure)
    result = st.session_state.get("apply_result")
    if result:
        _show_decision(result)
        _show_checks_and_documents(result)
        _show_enablement(result)


def render_lookup(client: ApiClient) -> None:
    st.caption("Enter the reference number together with the applicant's Emirates ID.")
    with st.form("lookup"):
        st.text_input("Reference number", key="lookup_reference", placeholder="SSA-XXXXXXXXXX")
        st.text_input("Emirates ID", key="lookup_emirates_id", placeholder="784-YYYY-NNNNNNN-N")
        st.form_submit_button("Look up", on_click=_lookup_application)

    if st.session_state.get("lookup_failure"):
        st.error(st.session_state.lookup_failure)
    result = st.session_state.get("lookup_result")
    if result:
        application = result["application"]
        decision = result["decision"]
        st.subheader(f"Application {result['reference_number']}")
        st.markdown(
            "\n".join(
                [
                    f"- **Name:** {application['full_name']}",
                    f"- **Emirates ID:** {application['emirates_id']}",
                    f"- **Family size:** {application['family_size']}",
                    f"- **Net monthly household income:** "
                    f"{application['net_monthly_income_aed']} AED",
                    f"- **Employment status:** "
                    f"{EMPLOYMENT_STATUSES[application['employment_status']]}",
                    f"- **Submitted:** {result['submitted_at']}",
                ]
            )
        )
        _show_decision(result, show_reference_hint=False)
        st.caption(f"Decided {decision['decided_at']} using rule {decision['rule_version']}.")


def _load_review_queue() -> None:
    state = st.session_state
    state.review_items, state.review_failure = None, None
    try:
        state.review_items = get_client().review_queue(state.review_passcode)["items"]
    except ApiError as exc:
        state.review_failure = exc.detail


def render_review(client: ApiClient) -> None:
    st.caption("For caseworkers. Enter the shared caseworker passcode.")
    with st.form("review"):
        st.text_input("Caseworker passcode", key="review_passcode", type="password")
        st.form_submit_button("Show review queue", on_click=_load_review_queue)

    if st.session_state.get("review_failure"):
        st.error(st.session_state.review_failure)
    items = st.session_state.get("review_items")
    if items is None:
        return
    if not items:
        st.info("No applications are waiting for review.")
        return
    st.markdown(f"**{len(items)} application(s) waiting for review**, newest first")
    st.table(
        [
            {
                "Reference": item["reference_number"],
                "Name": item["full_name"],
                "Submitted (UTC)": item["submitted_at"],
                "Flag reason": item["flag_reason"],
            }
            for item in items
        ]
    )
    for item in items:
        if item.get("reasons"):
            with st.expander(f"Reasons for {item['reference_number']}"):
                st.markdown("\n".join(f"- {reason}" for reason in item["reasons"]))


def main() -> None:
    st.set_page_config(page_title="Social Support Assessment", page_icon="🏛️")
    st.title("Social Support Assessment")
    client = get_client()
    apply_tab, lookup_tab, review_tab = st.tabs(["Apply", "Look up", "Review queue"])
    with apply_tab:
        render_apply(client)
    with lookup_tab:
        render_lookup(client)
    with review_tab:
        render_review(client)


main()
