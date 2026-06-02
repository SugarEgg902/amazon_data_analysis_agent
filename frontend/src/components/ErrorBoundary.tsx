import React from 'react'
import { Alert, Button } from 'antd'

interface State { hasError: boolean; message: string }

export default class ErrorBoundary extends React.Component<
  { children: React.ReactNode }, State
> {
  state: State = { hasError: false, message: '' }

  static getDerivedStateFromError(e: Error): State {
    return { hasError: true, message: e.message }
  }

  render() {
    if (this.state.hasError) {
      return (
        <Alert
          type="error"
          message="页面出错"
          description={this.state.message}
          action={
            <Button onClick={() => this.setState({ hasError: false, message: '' })}>
              重试
            </Button>
          }
        />
      )
    }
    return this.props.children
  }
}
