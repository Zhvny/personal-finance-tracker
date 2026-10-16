import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import * as matchers from "@testing-library/jest-dom/matchers";
import ButterflyErrorBoundary, { ButterflyStatus } from "../src/components/ButterflyErrorBoundary.jsx";

expect.extend(matchers);

describe("ButterflyStatus component", () => {
  it("renders status message", () => {
    render(<ButterflyStatus type="error" message="Test Error Message" />);
    expect(screen.getByText("Test Error Message")).toBeInTheDocument();
  });

  it("calls onRetry callback when retry button is clicked", () => {
    const handleRetry = vi.fn();
    render(<ButterflyStatus type="error" message="Error occurred" onRetry={handleRetry} />);
    
    const button = screen.getByRole("button", { name: /RETRY/i });
    expect(button).toBeInTheDocument();
    
    fireEvent.click(button);
    expect(handleRetry).toHaveBeenCalledTimes(1);
  });
});

describe("ButterflyErrorBoundary component", () => {
  it("renders children when there are no errors", () => {
    render(
      <ButterflyErrorBoundary message="Something crashed">
        <div data-testid="child-content">Safe Child Content</div>
      </ButterflyErrorBoundary>
    );

    expect(screen.getByTestId("child-content")).toBeInTheDocument();
    expect(screen.queryByText("Something crashed")).not.toBeInTheDocument();
  });

  it("renders fallback UI and manages details toggle/retry lifecycle", () => {
    const boundaryRef = React.createRef();

    render(
      <ButterflyErrorBoundary ref={boundaryRef} message="Graphics Engine Offline">
        <div data-testid="child-content">Safe Child Content</div>
      </ButterflyErrorBoundary>
    );

    // Verify initial render
    expect(screen.getByTestId("child-content")).toBeInTheDocument();
    expect(screen.queryByText("Graphics Engine Offline")).not.toBeInTheDocument();

    // Trigger state programmatically (re-rendering safe components to test boundary lifecycle)
    act(() => {
      boundaryRef.current.setState({
        hasError: true,
        error: new Error("Mocked WebGL Context Lost")
      });
    });

    // Verify fallback UI is rendered
    expect(screen.queryByTestId("child-content")).not.toBeInTheDocument();
    expect(screen.getByText("Graphics Engine Offline")).toBeInTheDocument();

    // Verify technical details toggle works
    const toggleButton = screen.getByRole("button", { name: /details/i });
    expect(toggleButton).toHaveTextContent(/Show technical details/i);
    expect(screen.queryByText(/Exception trace/i)).not.toBeInTheDocument();

    // Click to show details
    fireEvent.click(toggleButton);
    expect(toggleButton).toHaveTextContent(/Hide technical details/i);
    expect(screen.getByText(/Exception trace/i)).toBeInTheDocument();
    expect(screen.getByText(/Mocked WebGL Context Lost/i)).toBeInTheDocument();

    // Click to hide details
    fireEvent.click(toggleButton);
    expect(toggleButton).toHaveTextContent(/Show technical details/i);
    expect(screen.queryByText(/Exception trace/i)).not.toBeInTheDocument();

    // Verify retry functionality resets the boundary state
    const retryButton = screen.getByRole("button", { name: /RETRY/i });
    expect(retryButton).toBeInTheDocument();

    fireEvent.click(retryButton);

    // State should be reset
    expect(boundaryRef.current.state.hasError).toBe(false);
    expect(boundaryRef.current.state.error).toBeNull();
    expect(boundaryRef.current.state.showDetails).toBe(false);

    // Safe child content should be back in the document
    expect(screen.getByTestId("child-content")).toBeInTheDocument();
  });

  it("displays copy error button and copies error to clipboard when clicked", async () => {
    const boundaryRef = React.createRef();

    // Mock clipboard API
    const mockWriteText = vi.fn().mockResolvedValue(undefined);
    const originalClipboard = navigator.clipboard;
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText: mockWriteText },
      writable: true,
      configurable: true,
    });

    // Mock alert
    const mockAlert = vi.spyOn(window, "alert").mockImplementation(() => {});

    render(
      <ButterflyErrorBoundary ref={boundaryRef} message="Graphics Engine Offline">
        <div data-testid="child-content">Safe Child Content</div>
      </ButterflyErrorBoundary>
    );

    // Trigger error state programmatically
    const simulatedError = new Error("Mocked WebGL Context Lost");
    act(() => {
      boundaryRef.current.setState({
        hasError: true,
        error: simulatedError
      });
    });

    // Verify fallback UI is rendered
    expect(screen.getByText("Graphics Engine Offline")).toBeInTheDocument();

    // Open technical details first to see the trace and copy button
    const toggleButton = screen.getByRole("button", { name: /details/i });
    fireEvent.click(toggleButton);

    // Verify copy button is visible
    const copyButton = screen.getByRole("button", { name: /COPY ERROR/i });
    expect(copyButton).toBeInTheDocument();

    // Click the copy button
    fireEvent.click(copyButton);

    // Verify writeText was called with correct error stack
    expect(mockWriteText).toHaveBeenCalledWith(simulatedError.stack);

    // Restore mocks
    Object.defineProperty(navigator, "clipboard", {
      value: originalClipboard,
      writable: true,
      configurable: true,
    });
    mockAlert.mockRestore();
  });
});

