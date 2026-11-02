"""Errors a real LLM client raises. Agents catch these and fall back; nothing here carries an API key."""


class LLMError(Exception):
    """The model could not be reached or answered with an error."""


class LLMRateLimited(LLMError):
    """The provider kept answering HTTP 429 after every attempt."""


class LLMBadReply(LLMError):
    """The model answered, but the reply is not a JSON object."""
