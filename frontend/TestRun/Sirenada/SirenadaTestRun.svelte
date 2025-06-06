    <script>
    import { onMount, onDestroy, createEventDispatcher } from "svelte";
    import Fa from "svelte-fa";
    import {
        faClipboard,
        faCodeBranch,
        faComments,
        faExclamationTriangle,
        faInfoCircle,
        faRefresh,
        faTimes,
    } from "@fortawesome/free-solid-svg-icons";
    import ActivityTab from "../ActivityTab.svelte";
    import TestRunComments from "../TestRunComments.svelte";
    import { sendMessage } from "../../Stores/AlertStore";
    import { fetchRun } from "../../Common/RunUtils";
    import RunStatusButton from "../RunStatusButton.svelte";
    import RunInvestigationStatusButton from "../RunInvestigationStatusButton.svelte";
    import RunAssigneeSelector from "../RunAssigneeSelector.svelte";
    import SirenadaRunInfo from "./SirenadaRunInfo.svelte";
    import SirenadaTestBreakdown from "./SirenadaTestBreakdown.svelte";
    import IssueTab from "../IssueTab.svelte";
    import SirenadaIssueTemplate from "./SirenadaIssueTemplate.svelte";

    export let runId = "";
    export let buildNumber = -1;
    export let testInfo = {};
    export let tab = "";
    const dispatch = createEventDispatcher();
    let testRun = undefined;
    let runRefreshInterval;
    let activeTab = tab.toLowerCase() || "details";
    let failedToLoad = false;

    // Track which tabs have been visited
    let visitedTabs = {};
    visitedTabs[activeTab] = true;

    const setActiveTab = (tabName) => {
        tabName = tabName.toLowerCase();
        if (tabName !== activeTab) {
            activeTab = tabName;
            visitedTabs[tabName] = true;
            if (!window.location.pathname.startsWith("/workspace")) {
                const newUrl = `/tests/${testInfo.test.plugin_name}/${runId}/${tabName}`;
                history.replaceState({}, "", newUrl);
            }
        }
    };

    const fetchTestRunData = async function () {
        try {
            let run = await fetchRun(testInfo.test.plugin_name, runId);
            testRun = run;
            if (!testRun) {
                failedToLoad = true;
                return;
            }
            if (buildNumber == -1) {
                buildNumber = parseInt(
                    testRun.build_job_url.split("/").reverse()[1]
                );
            }
        } catch (error) {
            if (error?.status === "error") {
                sendMessage(
                    "error",
                    `API Error when fetching test run data.\nMessage: ${error.response.arguments[0]}`,
                    "SirenadaTestRun::fetchTestRunData"
                );
            } else {
                sendMessage(
                    "error",
                    "A backend error occurred during test run data fetch",
                    "SirenadaTestRun::fetchTestRunData"
                );
            }
        }
    };

    onMount(() => {
        fetchTestRunData();

        runRefreshInterval = setInterval(() => {
            fetchTestRunData();
        }, 1000 * 300);
    });

    onDestroy(() => {
        if (runRefreshInterval) clearInterval(runRefreshInterval);
    });
</script>

<div class="border rounded shadow-sm testrun-card mb-4 top-bar">
    <div class="d-flex px-2 py-2 mb-1 border-bottom bg-white ">
        <div class="p-1">
            {#if testRun}
                <a class="link-dark" href="/tests/{testInfo.test.plugin_name}/{testRun.id}">
                    {testRun.build_id}#{buildNumber}
                </a>
            {/if}
        </div>
        <div class="ms-auto text-end">
            <button class="btn btn-sm btn-outline-dark" title="Refresh" on:click={() => {
                fetchTestRunData();
            }}
                ><Fa icon={faRefresh} /></button
            >
        </div>
        <div class="ms-2 text-end">
            <button class="btn btn-sm btn-outline-dark" title="Close" on:click={() => {
                dispatch("closeRun", { id: runId });
            }}
                ><Fa icon={faTimes} /></button
            >
        </div>
    </div>
    {#if testRun}
        <div class="p-2">
            <div class="row p-2">
                <div class="col-6">
                    <div class="d-flex align-items-center">
                        <RunStatusButton {testRun} on:statusUpdate={(e) => {
                            testRun.status = e.detail.status;
                            dispatch("runStatusChange");
                        }} />
                        <RunInvestigationStatusButton {testRun} on:investigationStatusChange={(e) => {
                            testRun.investigation_status = e.detail.status;
                            dispatch("investigationStatusChange", e.detail);
                        }}/>
                    </div>
                </div>
                <div class="col-6">
                    <RunAssigneeSelector {testRun} on:assigneeUpdate={(e) => {
                        testRun.assignee = e.detail.assignee;
                    }} />
                </div>
            </div>
            <nav>
                <div class="nav nav-tabs" id="nav-tab-{runId}" role="tablist">
                    <button
                        class="nav-link"
                        class:active={activeTab === 'details'}
                        id="nav-details-tab-{runId}"
                        data-bs-toggle="tab"
                        data-bs-target="#nav-details-{runId}"
                        type="button"
                        role="tab"
                        on:click={() => setActiveTab("details")}
                        on:keydown={(e) => e.key === "Enter" && setActiveTab("details")}
                        ><Fa icon={faInfoCircle}/> Details</button
                    >
                    <button
                        class="nav-link"
                        class:active={activeTab === 'results'}
                        id="nav-results-tab-{runId}"
                        data-bs-toggle="tab"
                        data-bs-target="#nav-results-{runId}"
                        type="button"
                        role="tab"
                        on:click={() => setActiveTab("results")}
                        on:keydown={(e) => e.key === "Enter" && setActiveTab("results")}
                        ><Fa icon={faClipboard}/> Results</button
                    >
                    <button
                        class="nav-link"
                        class:active={activeTab === 'discuss'}
                        id="nav-discuss-tab-{runId}"
                        data-bs-toggle="tab"
                        data-bs-target="#nav-discuss-{runId}"
                        type="button"
                        on:click={() => setActiveTab("discuss")}
                        on:keydown={(e) => e.key === "Enter" && setActiveTab("discuss")}
                        role="tab"
                        ><Fa icon={faComments}/> Discussion</button
                    >
                    <button
                        class="nav-link"
                        class:active={activeTab === 'issues'}
                        id="nav-issues-tab-{runId}"
                        data-bs-toggle="tab"
                        data-bs-target="#nav-issues-{runId}"
                        type="button"
                        role="tab"
                        on:click={() => setActiveTab("issues")}
                        on:keydown={(e) => e.key === "Enter" && setActiveTab("issues")}
                        ><Fa icon={faCodeBranch}/> Issues</button
                    >
                    <button
                        class="nav-link"
                        class:active={activeTab === 'activity'}
                        id="nav-activity-tab-{runId}"
                        data-bs-toggle="tab"
                        data-bs-target="#nav-activity-{runId}"
                        type="button"
                        on:click={() => setActiveTab("activity")}
                        on:keydown={(e) => e.key === "Enter" && setActiveTab("activity")}
                        role="tab"
                        ><Fa icon={faExclamationTriangle}/> Activity</button
                    >
                </div>
            </nav>
            <div
                class="tab-content border-start border-end border-bottom bg-white"
                id="nav-tabContent-{runId}"
            >
                <div
                    class="tab-pane fade"
                    class:show={activeTab === 'details'}
                    class:active={activeTab === 'details'}
                    id="nav-details-{runId}"
                    role="tabpanel"
                >
                    <SirenadaRunInfo testRun={testRun} {testInfo}/>
                </div>
                <div
                    class="tab-pane fade"
                    class:show={activeTab === 'results'}
                    class:active={activeTab === 'results'}
                    id="nav-results-{runId}"
                    role="tabpanel"
                >
                    <SirenadaTestBreakdown {testRun} />
                </div>
                <div
                    class="tab-pane fade"
                    class:show={activeTab === 'discuss'}
                    class:active={activeTab === 'discuss'}
                    id="nav-discuss-{runId}"
                    role="tabpanel"
                >
                    {#if visitedTabs['discuss']}
                        <TestRunComments {testRun} {testInfo}/>
                    {/if}
                </div>
                <div
                    class="tab-pane fade"
                    class:show={activeTab === 'issues'}
                    class:active={activeTab === 'issues'}
                    id="nav-issues-{runId}"
                    role="tabpanel"
                >
                    <SirenadaIssueTemplate test_run={testRun} test={testInfo.test} />
                    <div class="py-2 bg-white">
                        {#if visitedTabs['issues']}
                            <IssueTab {testInfo} {runId} />
                        {/if}
                    </div>
                </div>
                <div
                    class="tab-pane fade"
                    class:show={activeTab === 'activity'}
                    class:active={activeTab === 'activity'}
                    id="nav-activity-{runId}"
                    role="tabpanel"
                >
                    {#if visitedTabs['activity']}
                        <ActivityTab id={runId} />
                    {/if}
                </div>
            </div>
        </div>
    {:else if failedToLoad}
        <div
            class="text-center p-2 m-1 d-flex align-items-center justify-content-center"
        >
            <span class="fs-4"
                >Run not found.</span
            >
        </div>
    {:else}
        <div
            class="text-center p-2 m-1 d-flex align-items-center justify-content-center"
        >
            <span class="spinner-border me-4" /><span class="fs-4"
                >Loading...</span
            >
        </div>
    {/if}
</div>

<style>
    .testrun-card {
        background-color: #ededed;
    }

    .top-bar {
        overflow: hidden;
    }
</style>
