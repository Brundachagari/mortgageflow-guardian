# Observability: custom metrics, alarms, and a dashboard.
#
# The TRE guide emphasizes proactive monitoring and automated incident response.
# Here we (1) turn structured logs into custom metrics, (2) raise alarms when
# something goes wrong, and (3) put it all on one dashboard.

# ---- Custom metrics from the processor's JSON logs -------------------------
# The processor logs one JSON object per event. A metric filter counts the ones
# we care about and turns them into CloudWatch metrics.

resource "aws_cloudwatch_log_metric_filter" "processed" {
  name           = "${local.name_prefix}-documents-processed"
  log_group_name = aws_cloudwatch_log_group.processor.name
  pattern        = "{ $.event = \"document_stored\" }"

  metric_transformation {
    name      = "DocumentsProcessed"
    namespace = "MortgageFlowGuardian"
    value     = "1"
  }
}

resource "aws_cloudwatch_log_metric_filter" "duplicates" {
  name           = "${local.name_prefix}-duplicates-detected"
  log_group_name = aws_cloudwatch_log_group.processor.name
  pattern        = "{ $.event = \"duplicate_detected\" }"

  metric_transformation {
    name      = "DuplicatesDetected"
    namespace = "MortgageFlowGuardian"
    value     = "1"
  }
}

# ---- Alarms: tell us the moment something breaks ---------------------------

resource "aws_cloudwatch_metric_alarm" "processor_errors" {
  alarm_name          = "${local.name_prefix}-processor-errors"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "Processor Lambda raised an error."
  treat_missing_data  = "notBreaching"
  dimensions          = { FunctionName = aws_lambda_function.processor.function_name }
}

resource "aws_cloudwatch_metric_alarm" "dlq_not_empty" {
  alarm_name          = "${local.name_prefix}-dlq-not-empty"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Maximum"
  threshold           = 1
  alarm_description   = "A document landed in the dead-letter queue and needs attention."
  treat_missing_data  = "notBreaching"
  dimensions          = { QueueName = aws_sqs_queue.dlq.name }
}

resource "aws_cloudwatch_metric_alarm" "workflow_failures" {
  alarm_name          = "${local.name_prefix}-workflow-failures"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "ExecutionsFailed"
  namespace           = "AWS/States"
  period              = 300
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "A Step Functions execution failed."
  treat_missing_data  = "notBreaching"
  dimensions          = { StateMachineArn = aws_sfn_state_machine.pipeline.arn }
}

# ---- Dashboard: one screen showing the whole system's health ---------------

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${local.name_prefix}-overview"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "Documents processed vs duplicates"
          region = var.aws_region
          view   = "timeSeries"
          metrics = [
            ["MortgageFlowGuardian", "DocumentsProcessed"],
            ["MortgageFlowGuardian", "DuplicatesDetected"]
          ]
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "Lambda errors & duration (processor)"
          region = var.aws_region
          view   = "timeSeries"
          metrics = [
            ["AWS/Lambda", "Errors", "FunctionName", aws_lambda_function.processor.function_name],
            ["AWS/Lambda", "Duration", "FunctionName", aws_lambda_function.processor.function_name]
          ]
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "Queue depth: processing vs dead-letter"
          region = var.aws_region
          view   = "timeSeries"
          metrics = [
            ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", aws_sqs_queue.processing.name],
            ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", aws_sqs_queue.dlq.name]
          ]
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "Workflow executions (succeeded vs failed)"
          region = var.aws_region
          view   = "timeSeries"
          metrics = [
            ["AWS/States", "ExecutionsSucceeded", "StateMachineArn", aws_sfn_state_machine.pipeline.arn],
            ["AWS/States", "ExecutionsFailed", "StateMachineArn", aws_sfn_state_machine.pipeline.arn]
          ]
        }
      }
    ]
  })
}
