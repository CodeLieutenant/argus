<script>
    import { createEventDispatcher, } from "svelte";
    /**
     * @type {{
     * result: Object | undefined
     * }} args
     */
    export let args;
    const dispatch = createEventDispatcher();

</script>

<div>
    {#if args.result}
        <div class="mb-6">
            <h6>Clone successful!</h6>
            <div>
                Created <a href="{args.result.new_job.url}">{args.result.new_entity.build_system_id}</a>.
            </div>
        </div>
        <div>
            <button class="btn btn-success w-100" on:click={() => {
                dispatch("exit", {
                    newBuildId: args.result.new_entity.build_system_id,
                    newTestId: args.result.new_entity.id,
                });
            }}>Next</button>
        </div>
    {/if}
</div>
