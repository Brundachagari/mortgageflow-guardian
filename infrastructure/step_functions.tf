# The Step Functions state machine -- the "conductor" of the pipeline.
#
# The workflow itself is defined in state_machine.asl.json (Amazon States
# Language). `templatefile` injects the real ARNs into that JSON at deploy time.
# Using Step Functions instead of one giant Lambda means each step is visible in
# the console, retries are declarative, and failures are caught and dead-lettered
# without extra code.

resource "aws_cloudwatch_log_group" "sfn" {
  name              = "/aws/vendedlogs/states/${local.name_prefix}-pipeline"
  retention_in_days = var.log_retention_days
}

resource "aws_sfn_state_machine" "pipeline" {
  name     = "${local.name_prefix}-pipeline"
  role_arn = aws_iam_role.sfn.arn

  definition = templatefile("${path.module}/state_machine.asl.json", {
    processor_arn = aws_lambda_function.processor.arn
    topic_arn     = aws_sns_topic.review.arn
    dlq_url       = aws_sqs_queue.dlq.id
  })

  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.sfn.arn}:*"
    include_execution_data = false
    level                  = "ERROR"
  }
}
