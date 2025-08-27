import React, { useState, useEffect } from 'react';
import { 
  Button, 
  Upload, 
  Progress, 
  Card, 
  Form, 
  Input, 
  InputNumber, 
  Switch,
  message,
  Typography,
  Space,
  Alert,
  Table,
  Tag
} from 'antd';
import { InboxOutlined, FileTextOutlined, CheckCircleOutlined, SyncOutlined } from '@ant-design/icons';
import './PDFProcessor.css';

const { Title, Text, Paragraph } = Typography;
const { Dragger } = Upload;

/**
 * PDF Policy Processor Component
 * 
 * Advanced interface for uploading and processing PDF files into policy documents
 * with real-time progress tracking and visualization.
 */
const PDFProcessor = () => {
  // Component state
  const [form] = Form.useForm();
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [taskId, setTaskId] = useState(null);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [policies, setPolicies] = useState([]);
  const [loading, setLoading] = useState(false);
  
  // Event source for streaming updates
  const [eventSource, setEventSource] = useState(null);

  // Fetch existing policies on component mount
  useEffect(() => {
    fetchPolicies();
  }, []);
  
  // Clean up event source on unmount
  useEffect(() => {
    return () => {
      if (eventSource) {
        eventSource.close();
      }
    };
  }, [eventSource]);
  
  // Set up streaming updates when task ID changes
  useEffect(() => {
    if (taskId) {
      const source = new EventSource(`/api/v1/pdf/stream/${taskId}`);
      
      source.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.status === 'error') {
          setStatus('error');
          setError(data.error || 'An error occurred during processing');
          source.close();
        } else if (data.status === 'completed' || data.status === 'processed') {
          setStatus(data.status);
          setProgress(100);
          setResult(data.result);
          source.close();
          
          // Refresh policies list
          fetchPolicies();
        } else if (data.progress) {
          setStatus(data.status);
          setProgress(data.progress.percentage);
        }
      };
      
      source.onerror = () => {
        source.close();
        setError('Connection to server lost');
      };
      
      setEventSource(source);
      
      return () => {
        source.close();
      };
    }
  }, [taskId]);
  
  // Fetch existing policies
  const fetchPolicies = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/v1/pdf/policies');
      const data = await response.json();
      setPolicies(data);
    } catch (error) {
      message.error('Failed to fetch policies');
    } finally {
      setLoading(false);
    }
  };
  
  // Handle file upload and process
  const handleUpload = async (values) => {
    if (!file) {
      message.error('Please select a PDF file first');
      return;
    }
    
    setUploading(true);
    setError(null);
    
    try {
      // Create form data
      const formData = new FormData();
      formData.append('file', file);
      
      // Add form values
      const requestData = {
        title: values.title,
        issuer: values.issuer,
        min_tokens: values.min_tokens,
        max_tokens: values.max_tokens,
        store_in_db: values.store_in_db
      };
      
      // Add form values as query parameters
      const params = new URLSearchParams();
      Object.entries(requestData).forEach(([key, value]) => {
        params.append(key, value);
      });
      
      // Send the request
      const response = await fetch(`/api/v1/pdf/process?${params.toString()}`, {
        method: 'POST',
        body: formData
      });
      
      if (!response.ok) {
        throw new Error('Failed to upload file');
      }
      
      const data = await response.json();
      setTaskId(data.task_id);
      setStatus('processing');
      
    } catch (error) {
      setError(error.message);
      message.error('Upload failed');
    } finally {
      setUploading(false);
    }
  };
  
  // Handle upload file change
  const handleFileChange = (info) => {
    if (info.file.status === 'removed') {
      setFile(null);
      return;
    }
    
    setFile(info.file.originFileObj);
  };
  
  // Handle reset
  const handleReset = () => {
    setFile(null);
    setTaskId(null);
    setProgress(0);
    setStatus(null);
    setResult(null);
    setError(null);
    form.resetFields();
    
    if (eventSource) {
      eventSource.close();
      setEventSource(null);
    }
  };
  
  // Policy table columns
  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      render: (id) => <Text copyable>{id}</Text>
    },
    {
      title: 'Title',
      dataIndex: 'title',
      key: 'title'
    },
    {
      title: 'Issuer',
      dataIndex: 'issuer',
      key: 'issuer'
    },
    {
      title: 'Status',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (isActive) => (
        isActive ? 
          <Tag color="green">Active</Tag> : 
          <Tag color="red">Inactive</Tag>
      )
    },
    {
      title: 'Chunks',
      dataIndex: 'chunk_count',
      key: 'chunk_count'
    }
  ];
  
  return (
    <div className="pdf-processor">
      <Title level={2}>PDF Policy Processor</Title>
      
      <div className="pdf-processor-container">
        <div className="upload-section">
          <Card title="Upload PDF Document" bordered={false}>
            <Form
              form={form}
              layout="vertical"
              onFinish={handleUpload}
              initialValues={{
                issuer: 'Organization',
                min_tokens: 200,
                max_tokens: 400,
                store_in_db: true
              }}
            >
              <Dragger
                name="file"
                accept=".pdf"
                multiple={false}
                beforeUpload={() => false}
                onChange={handleFileChange}
                disabled={uploading || status === 'processing'}
              >
                <p className="ant-upload-drag-icon">
                  <InboxOutlined />
                </p>
                <p className="ant-upload-text">Click or drag PDF file to this area to upload</p>
                <p className="ant-upload-hint">
                  Support for single PDF file upload. File will be processed into policy chunks.
                </p>
              </Dragger>
              
              {file && (
                <div className="file-info">
                  <FileTextOutlined /> {file.name}
                </div>
              )}
              
              <Form.Item
                label="Policy Title"
                name="title"
                tooltip="Leave blank to use PDF title or filename"
              >
                <Input placeholder="Optional: Policy Title" />
              </Form.Item>
              
              <Form.Item
                label="Issuer"
                name="issuer"
                rules={[{ required: true, message: 'Please input the issuer!' }]}
              >
                <Input placeholder="Organization name" />
              </Form.Item>
              
              <Form.Item label="Advanced Settings">
                <div className="advanced-settings">
                  <Form.Item
                    label="Min Tokens"
                    name="min_tokens"
                    className="inline-form-item"
                  >
                    <InputNumber min={50} max={1000} />
                  </Form.Item>
                  
                  <Form.Item
                    label="Max Tokens"
                    name="max_tokens"
                    className="inline-form-item"
                  >
                    <InputNumber min={100} max={2000} />
                  </Form.Item>
                </div>
              </Form.Item>
              
              <Form.Item
                label="Store in Database"
                name="store_in_db"
                valuePropName="checked"
              >
                <Switch />
              </Form.Item>
              
              <Form.Item>
                <Space>
                  <Button
                    type="primary"
                    htmlType="submit"
                    loading={uploading}
                    disabled={!file || status === 'processing'}
                  >
                    Process PDF
                  </Button>
                  
                  <Button onClick={handleReset}>
                    Reset
                  </Button>
                </Space>
              </Form.Item>
            </Form>
          </Card>
        </div>
        
        <div className="result-section">
          <Card title="Processing Status" bordered={false}>
            {status && (
              <>
                <div className="status-display">
                  <Text>Status: </Text>
                  {status === 'processing' && <Tag icon={<SyncOutlined spin />} color="processing">Processing</Tag>}
                  {status === 'completed' && <Tag icon={<CheckCircleOutlined />} color="success">Completed</Tag>}
                  {status === 'processed' && <Tag icon={<CheckCircleOutlined />} color="success">Processed</Tag>}
                  {status === 'error' && <Tag color="error">Error</Tag>}
                </div>
                
                <Progress percent={progress} status={status === 'error' ? 'exception' : undefined} />
                
                {error && (
                  <Alert
                    message="Processing Error"
                    description={error}
                    type="error"
                    showIcon
                  />
                )}
                
                {result && (
                  <div className="result-info">
                    <Paragraph>
                      <Text strong>Policy ID:</Text> <Text copyable>{result.policy_id}</Text>
                    </Paragraph>
                    <Paragraph>
                      <Text strong>Chunks Created:</Text> {result.chunk_count}
                    </Paragraph>
                    <Paragraph>
                      <Text strong>Total Tokens:</Text> {result.total_tokens}
                    </Paragraph>
                  </div>
                )}
              </>
            )}
            
            {!status && (
              <div className="empty-status">
                <Text type="secondary">Upload and process a PDF to see status here</Text>
              </div>
            )}
          </Card>
          
          <Card title="Existing Policies" className="policies-table" bordered={false}>
            <Table
              dataSource={policies}
              columns={columns}
              rowKey="id"
              loading={loading}
              pagination={{ pageSize: 5 }}
            />
          </Card>
        </div>
      </div>
    </div>
  );
};

export default PDFProcessor;
