# The two Lambda functions and how they are packaged and triggered.
#
# Packaging: scripts/build_lambdas.sh copies src/ (plus the pydantic dependency
# for the processor) into build/<function>/. The archive_file data source below
# zips that folder. So the workflow is:  build script -> zip -> deploy.
# Run the build script BEFORE `terraform apply`.

data "archive_file" "ingestion" {
  type        = "zip"
  source_dir  = "${path.module}/../build/ingestion"
  output_path = "${path.module}/build/ingestion.zip"
}

data "archive_file" "processor" {
  type        = "zip"
  source_dir  = "${path.module}/../build/processor"
  output_path = "${path.module}/build/processor.zip"
}

# ---- Ingestion function: SQS-triggered, starts the workflow ----------------
resource "aws_lambda_function" "ingestion" {
  function_name    = "${local.name_prefix}-ingestion"
  role             = aws_iam_role.ingestion.arn
  runtime          = var.lambda_runtime
  handler          = "ingestion.handler.handler"
  filename         = data.archive_file.ingestion.output_path
  source_code_hash = data.archive_file.ingestion.output_base64sha256
  timeout          = 30
  memory_size      = 256

  environment {
    variables = {
      STATE_MACHINE_ARN  = aws_sfn_state_machine.pipeline.arn
      ALLOWED_EXTENSIONS = var.allowed_extensions
      MAX_FILE_MB        = tostring(var.max_file_mb)
    }
  }
}

# Wire the processing queue to the ingestion Lambda (event source mapping).
resource "aws_lambda_event_source_mapping" "queue_to_ingestion" {
  event_source_arn = aws_sqs_queue.processing.arn
  function_name    = aws_lambda_function.ingestion.arn
  batch_size       = 10
}

# ---- Processor function: the Step Functions task ---------------------------
resource "aws_lambda_function" "processor" {
  function_name    = "${local.name_prefix}-processor"
  role             = aws_iam_role.processor.arn
  runtime          = var.lambda_runtime
  handler          = "processing.handler.handler"
  filename         = data.archive_file.processor.output_path
  source_code_hash = data.archive_file.processor.output_base64sha256
  timeout          = 30
  memory_size      = 256

  environment {
    variables = {
      DOCUMENTS_TABLE = aws_dynamodb_table.documents.name
    }
  }
}

# ---- Log groups (created explicitly so we control retention) ---------------
resource "aws_cloudwatch_log_group" "ingestion" {
  name              = "/aws/lambda/${local.name_prefix}-ingestion"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "processor" {
  name              = "/aws/lambda/${local.name_prefix}-processor"
  retention_in_days = var.log_retention_days
}
