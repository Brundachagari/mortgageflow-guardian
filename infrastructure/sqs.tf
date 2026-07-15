# The processing queue (buffer) and the dead-letter queue (safety net).
#
# Why a queue at all? It decouples "a file arrived" from "process the file". If
# 500 files land at once, they wait politely in line instead of overwhelming the
# AI/compute layer. If processing is briefly broken, the work is preserved.

# Dead-letter queue: the final resting place for messages that cannot be
# processed. Nothing is ever silently dropped -- a human can inspect these.
resource "aws_sqs_queue" "dlq" {
  name                      = "${local.name_prefix}-dlq"
  message_retention_seconds = 1209600 # 14 days, the maximum
  sqs_managed_sse_enabled   = true    # encrypt messages at rest
}

# Main processing queue. After a message fails to process 5 times (a "poison"
# message), SQS automatically moves it to the dead-letter queue above.
resource "aws_sqs_queue" "processing" {
  name                       = "${local.name_prefix}-processing"
  visibility_timeout_seconds = 180 # must exceed the Lambda timeout
  sqs_managed_sse_enabled    = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = 5
  })
}

# Allow the S3 bucket (and only it) to send messages to the processing queue.
resource "aws_sqs_queue_policy" "allow_s3" {
  queue_url = aws_sqs_queue.processing.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowS3SendMessage"
      Effect    = "Allow"
      Principal = { Service = "s3.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.processing.arn
      Condition = {
        ArnLike      = { "aws:SourceArn" = aws_s3_bucket.documents.arn }
        StringEquals = { "aws:SourceAccount" = data.aws_caller_identity.current.account_id }
      }
    }]
  })
}
