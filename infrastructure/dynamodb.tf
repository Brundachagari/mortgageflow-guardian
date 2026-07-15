# The document record store.
#
# Why DynamoDB (a key-value store) instead of a relational database? Our access
# patterns are simple key lookups -- "get document by id", "find by hash",
# "list by status" -- with no joins. DynamoDB gives single-digit-millisecond
# reads for exactly this shape, scales automatically, and (on-demand billing)
# costs nothing when idle. That trade-off is a strong interview talking point.

resource "aws_dynamodb_table" "documents" {
  name         = "${local.name_prefix}-documents"
  billing_mode = "PAY_PER_REQUEST" # pay per request; no idle cost
  hash_key     = "documentId"

  # Only attributes used as keys/indexes must be declared; the rest are schemaless.
  attribute {
    name = "documentId"
    type = "S"
  }
  attribute {
    name = "documentHash"
    type = "S"
  }
  attribute {
    name = "processingStatus"
    type = "S"
  }

  # Index that powers duplicate detection (look up a document by its content hash).
  global_secondary_index {
    name            = "documentHash-index"
    hash_key        = "documentHash"
    projection_type = "ALL"
  }

  # Index that powers "show me everything awaiting human review".
  global_secondary_index {
    name            = "processingStatus-index"
    hash_key        = "processingStatus"
    projection_type = "ALL"
  }

  # Lets you restore the table to any point in the last 35 days.
  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }
}
