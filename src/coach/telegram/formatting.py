import re


def _convert_markdown_tables(text: str) -> str:
    """
    Convert Markdown table blocks (lines starting with |) to <pre> blocks.
    Removes separator rows and wraps data rows in monospace formatting.
    """
    lines = text.split("\n")
    result = []
    i = 0

    while i < len(lines):
        # Check if this line starts a table (begins with |)
        if lines[i].strip().startswith("|"):
            table_lines = []
            # Collect consecutive | lines
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1

            # Filter out separator rows (contain only |, -, :, spaces)
            data_rows = [
                line
                for line in table_lines
                if not re.match(r"^\s*\|[\s|:-]+\|\s*$", line)
            ]

            if data_rows:
                # Wrap in <pre> for monospace rendering
                table_content = "\n".join(data_rows)
                result.append(f"<pre>{table_content}</pre>")
        else:
            result.append(lines[i])
            i += 1

    return "\n".join(result)


def markdown_to_html(text: str) -> str:
    """
    Convert Markdown syntax to Telegram HTML formatting.
    Handles: **bold**, *italic*, `code`, ```code blocks```, # headings, and tables.
    Leaves existing HTML tags untouched.
    """
    # 0. Markdown tables → <pre> blocks
    text = _convert_markdown_tables(text)

    # Use placeholders to protect code blocks from further processing
    # Use a format that won't be affected by Markdown conversion (no underscores)
    code_blocks = {}
    code_block_counter = 0

    # 1. Triple-backtick code blocks → placeholder, then <pre>...</pre> at the end
    def protect_code_block(match):
        nonlocal code_block_counter
        placeholder = f"CODEBLOCK{code_block_counter}CODEBLOCK"
        code_blocks[placeholder] = f"<pre>{match.group(1)}</pre>"
        code_block_counter += 1
        return placeholder

    text = re.sub(r"```([^`]+)```", protect_code_block, text, flags=re.DOTALL)

    # 2. Inline backtick code → placeholder, then <code>...</code> at the end
    inline_codes = {}
    inline_code_counter = 0

    def protect_inline_code(match):
        nonlocal inline_code_counter
        placeholder = f"INLINECODE{inline_code_counter}INLINECODE"
        inline_codes[placeholder] = f"<code>{match.group(1)}</code>"
        inline_code_counter += 1
        return placeholder

    text = re.sub(r"`([^`]+)`", protect_inline_code, text)

    # 3. **bold** and __bold__ → <b>bold</b>
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)

    # 4. *italic* and _italic_ → <i>italic</i>
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    text = re.sub(r"_(.+?)_", r"<i>\1</i>", text)

    # 5. # Heading (1–6 levels) at line start → <b>Heading</b>
    text = re.sub(
        r"^#{1,6}\s+(.+)$",
        r"<b>\1</b>",
        text,
        flags=re.MULTILINE,
    )

    # Restore code blocks and inline codes
    for placeholder, html in code_blocks.items():
        text = text.replace(placeholder, html)

    for placeholder, html in inline_codes.items():
        text = text.replace(placeholder, html)

    return text
