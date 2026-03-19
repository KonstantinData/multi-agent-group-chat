# Multi-Agent Group Chats and Planning with AutoGen

This chapter focuses on a sophisticated agentic design pattern: **multi-agent group chats** combined with a **planning agent**. Instead of requiring a human to design every concrete step of a task (as in sequential chat), this pattern allows agents to collaborate dynamically to solve complex problems, such as generating detailed stock performance reports.

## Core Concepts

### 1. Group Chat Conversation Pattern
Unlike sequential chats, a **Group Chat** allows multiple agents to work together without a human providing detailed instructions for every step. A specialized agent called the **Group Chat Manager** facilitates the conversation by broadcasting messages and using an LLM to decide which agent should speak next based on the history and agent roles.

### 2. The Planning Pattern
For complex tasks, a **Planner agent** is introduced to decompose the main goal into smaller, manageable sub-tasks. The planner determines what information is needed, suggests steps that can be achieved via Python code, and monitors progress after each step is completed.

## The Multi-Agent Team

The chapter demonstrates building a group chat with five distinct roles:

*   **Admin (User Proxy):** Initiates the task, sends instructions to the writer to refine content, and asks for human feedback.
*   **Planner:** Decomposes the task, determines necessary information, and instructs remaining steps after reviewing progress.
*   **Engineer:** A default assistant agent that writes Python code based on the plan provided by the Planner.
*   **Executor:** A conversable agent configured to execute the Python code written by the Engineer and output the results.
*   **Writer:** Responsible for drafting the final report or blog post in markdown format and refining it based on feedback.

## Defining Agent Roles vs. Instructions
A key lesson in this chapter is the distinction between a **system message** and a **description**:
*   **System Message:** Instructions intended only for the agent itself to follow.
*   **Description:** A high-level summary of the agent's role used by the **Group Chat Manager** to decide when that agent should be called upon to speak.

## Customizing Speaker Transitions

While the LLM often picks the best next speaker, it can sometimes skip steps or follow an inefficient order. Developers can add more control through **allowed or disallowed speaker transitions**.

*   **Finite State Machine (FSM) Simulation:** By specifying which agents are allowed to speak after others (e.g., only the Executor or Admin can speak after the Engineer), developers can enforce a more logical flow while maintaining flexibility.
*   **Constraints:** These constraints ensure the Planner has a chance to review data before the Writer begins, or that code is always executed before the next planning phase.

## Conclusion
Group chat provides a **dynamic and flexible** way for multiple agents to complete non-linear tasks. By carefully designing agent roles and utilizing planning agents and transition constraints, developers can build powerful collaborative systems that require less manual step-by-step design.
