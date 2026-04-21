/** 附件栏 — 上传模式 + 展示模式 */
import { useState } from 'react'
import { Upload, Button, List, Typography, Image, Modal, message, Progress } from 'antd'
import {
  UploadOutlined, DownloadOutlined, DeleteOutlined,
  FileOutlined, PictureOutlined,
} from '@ant-design/icons'
import { apiUploadAttach, apiDownloadAttach } from '../../api/client'
import { formatFileSize } from '../../utils/format'
import type { Attachment } from '../../types/mail'

const { Text } = Typography

const MAX_FILE_SIZE = 15 * 1024 * 1024 // 15MB

interface AttachmentBarProps {
  /** 写邮件模式 — 可上传 */
  mode: 'compose' | 'read'
  /** 已有附件列表 */
  attachments: Attachment[]
  /** 关联的 emailId（上传时用） */
  emailId?: string
  /** 上传成功后回调（返回新附件） */
  onAttachmentAdded?: (att: Attachment) => void
  /** 删除回调 */
  onAttachmentRemoved?: (attId: string) => void
}

export function AttachmentBar({
  mode, attachments, emailId,
  onAttachmentAdded, onAttachmentRemoved,
}: AttachmentBarProps) {
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [previewImg, setPreviewImg] = useState<string | null>(null)

  // 文件 → Base64
  const fileToBase64 = (file: File): Promise<string> =>
    new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => {
        const result = reader.result as string
        // 去掉 data:xxx;base64, 前缀
        resolve(result.split(',')[1])
      }
      reader.onerror = reject
      reader.readAsDataURL(file)
    })

  // 上传文件
  const handleUpload = async (file: File) => {
    if (file.size > MAX_FILE_SIZE) {
      message.error(`文件 ${file.name} 超过 15MB 限制`)
      return false
    }
    if (!emailId) {
      message.error('请先保存草稿后再上传附件')
      return false
    }
    setUploading(true)
    setUploadProgress(30)
    try {
      const base64 = await fileToBase64(file)
      setUploadProgress(60)
      const att = await apiUploadAttach(emailId, file.name, file.type || 'application/octet-stream', base64)
      setUploadProgress(100)
      onAttachmentAdded?.(att)
      message.success(`${file.name} 上传成功`)
    } catch {
      message.error(`${file.name} 上传失败`)
    } finally {
      setUploading(false)
      setUploadProgress(0)
    }
    return false // 阻止 antd 默认上传行为
  }

  // 下载
  const handleDownload = async (att: Attachment) => {
    try {
      const full = await apiDownloadAttach(att.attachment_id)
      if (!full.data) {
        message.error('附件数据为空')
        return
      }
      const binary = atob(full.data)
      const bytes = new Uint8Array(binary.length)
      for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i)
      }
      const blob = new Blob([bytes], { type: att.content_type })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = att.filename
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      message.error('下载失败')
    }
  }

  // 图片预览
  const handlePreview = async (att: Attachment) => {
    try {
      const full = await apiDownloadAttach(att.attachment_id)
      if (full.data) {
        setPreviewImg(`data:${att.content_type};base64,${full.data}`)
      }
    } catch {
      message.error('预览失败')
    }
  }

  const isImage = (contentType: string) => contentType.startsWith('image/')

  return (
    <div>
      {/* 上传区域 — compose 模式 */}
      {mode === 'compose' && (
        <div style={{ marginBottom: 12 }}>
          <Upload
            beforeUpload={handleUpload}
            showUploadList={false}
            multiple
          >
            <Button icon={<UploadOutlined />} loading={uploading}>
              添加附件
            </Button>
          </Upload>
          {uploading && <Progress percent={uploadProgress} size="small" style={{ marginTop: 4, maxWidth: 200 }} />}
        </div>
      )}

      {/* 附件列表 */}
      {attachments.length > 0 && (
        <List
          size="small"
          dataSource={attachments}
          renderItem={(att) => (
            <List.Item
              key={att.attachment_id}
              actions={[
                ...(isImage(att.content_type)
                  ? [
                      <Button
                        key="preview"
                        type="link"
                        size="small"
                        icon={<PictureOutlined />}
                        onClick={() => handlePreview(att)}
                      >
                        预览
                      </Button>,
                    ]
                  : []),
                <Button
                  key="download"
                  type="link"
                  size="small"
                  icon={<DownloadOutlined />}
                  onClick={() => handleDownload(att)}
                >
                  下载
                </Button>,
                ...(mode === 'compose'
                  ? [
                      <Button
                        key="delete"
                        type="link"
                        size="small"
                        danger
                        icon={<DeleteOutlined />}
                        onClick={() => onAttachmentRemoved?.(att.attachment_id)}
                      >
                        删除
                      </Button>,
                    ]
                  : []),
              ]}
            >
              <List.Item.Meta
                avatar={<FileOutlined style={{ fontSize: 20 }} />}
                title={att.filename}
                description={<Text type="secondary">{formatFileSize(att.file_size)}</Text>}
              />
            </List.Item>
          )}
        />
      )}

      {/* 图片预览 Modal */}
      <Modal
        open={!!previewImg}
        footer={null}
        onCancel={() => setPreviewImg(null)}
        width={800}
      >
        {previewImg && <Image src={previewImg} style={{ width: '100%' }} preview={false} />}
      </Modal>
    </div>
  )
}
