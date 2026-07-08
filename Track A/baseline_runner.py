#!/usr/bin/env python
# -*-coding:utf-8 -*-

from typing import Any, Dict, List

from utils import (
    print_model_response,
    print_tool_call,
    print_tool_result,
    extract_answer,
)


def run_baseline(runner: Any, scenario: Dict[str, Any], free_mode: bool = False) -> Dict[str, Any]:
    """
    Run the original single-agent baseline loop.

    This function intentionally reuses the existing AgentsRunner instance for:
    - model calls via runner._call_model(...)
    - tool execution via runner.environment.execute(...)
    - logging via runner.logger
    - verbosity and iteration settings
    """
    scenario_id = scenario.get("scenario_id")
    task = scenario.get("task", {})

    options_text = "".join([f"{item['id']}: {item['label']}\n" for item in task.get("options", [])])

    # tools from server
    tool_defs = runner.environment.get_tools()
    if not tool_defs:
        return {"scenario_id": scenario_id, "status": "unresolved", "reason": "No tools available"}

    question = task.get("description", "") + f"\nOptions:\n{options_text}"

    messages: List[Dict[str, Any]] = [{"role": "user", "content": question}]

    num_tool_calls = 0
    list_tool_calls = []
    status = None
    reason = None
    last_msg = None
    last_iteration = 0

    for i in range(runner.max_iterations):
        last_iteration = i + 1
        runner.logger.info(f"\n[Scenario: {scenario_id}] Round {i + 1} conversation, calling tools:")

        msg = runner._call_model(messages, functions=tool_defs)
        if msg is None:
            continue

        last_msg = msg
        messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": msg.tool_calls})

        if runner.verbose:
            print_model_response(msg, logger=runner.logger, minimize=False)

        # tool calls
        if msg.tool_calls:
            num_tool_calls += len(msg.tool_calls)

            for j, tool_call in enumerate(msg.tool_calls):
                if runner.verbose:
                    print_tool_call(tool_call, logger=runner.logger)

                tool_result = runner.environment.execute(tool_call, scenario_id=scenario_id)

                messages.append({"role": "tool", "content": tool_result, "tool_call_id": tool_call.id})

                if runner.verbose:
                    print_tool_result(tool_result, logger=runner.logger)

                has_failed = "error" in tool_result
                list_tool_calls.append(
                    {
                        "function_name": tool_call.function.name,
                        "arguments": tool_call.function.arguments,
                        "turn": i + 1,
                        "has_failed": has_failed,
                        "order": j + 1,
                        "results": tool_result
                    }
                )

        # final answer
        # elif msg.content or msg.reasoning_content:
        elif msg.content:
            status = "solved"
            break

        else:
            status = "unresolved"
            reason = "Unable to answer this question."
            break

    if status is None:
        status = "unresolved"
        reason = "The maximum number of iterations has been reached."

    # Optional final constraint prompt
    if free_mode:
        current_answer = getattr(last_msg, "content", "") or getattr(last_msg, "reasoning_content",
                                                                     "") if last_msg else "",
        current_traces = getattr(last_msg, "reasoning_content", "") if last_msg else ""
        agent_answer = extract_answer(current_answer) or extract_answer(current_traces)
        if agent_answer == "":
            runner.logger.info(f"\n[Scenario: {scenario_id}] Round {last_iteration + 1} conversation, answer question:")
            status = "solved"

            if 'Select the most appropriate optimization solution' in question:
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "This is a single-answer question. Select the most appropriate optimization solution and enclose its number in \\boxed{{}} "
                            f"in the final answer. For example, \\boxed{{C3}} \nPotential optimization actions:\n{options_text}\n"
                        ),
                    }
                )
            else:
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "This is a multiple-answer question. Select two to four possible optimization solutions and enclose their numbers in \\boxed{{}} "
                            f"in the final answer. For example,  \\boxed{{C3|C5}} or \\boxed{{C7|C11}}. \nPotential optimization actions:\n{options_text}\n"
                        ),
                    }
                )

            msg2 = runner._call_model(messages, functions=[])
            if msg2 is not None:
                last_msg = msg2

    return {
        "scenario_id": scenario_id,
        "num_iterations": last_iteration,
        "tool_calls": list_tool_calls,
        "num_tool_calls": num_tool_calls,
        "status": status,
        "traces": getattr(last_msg, "reasoning_content", "") if last_msg else "",
        "answer": getattr(last_msg, "content", "") or getattr(last_msg, "reasoning_content", "") if last_msg else "",
        "messages": messages,
        "reason": reason,
        "architecture": "baseline",
    }
