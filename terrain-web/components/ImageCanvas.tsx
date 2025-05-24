import { useRef, useEffect, useState } from 'react';

export default function ImageCanvas({ imageSrc, onColorPick, onBoundsDraw }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [img, setImg] = useState<HTMLImageElement | null>(null);
  const [start, setStart] = useState<[number, number] | null>(null);

  useEffect(() => {
    const image = new Image();
    image.src = imageSrc;
    image.onload = () => setImg(image);
  }, [imageSrc]);

  useEffect(() => {
    if (!img || !canvasRef.current) return;
    const ctx = canvasRef.current.getContext('2d');
    if (!ctx) return;
    ctx.drawImage(img, 0, 0, img.width, img.height);
  }, [img]);

  const handleClick = (e: React.MouseEvent) => {
    const canvas = canvasRef.current;
    if (!canvas || !img) return;
    const rect = canvas.getBoundingClientRect();
    const x = Math.floor(e.clientX - rect.left);
    const y = Math.floor(e.clientY - rect.top);
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const [r, g, b] = ctx.getImageData(x, y, 1, 1).data;
    onColorPick([r, g, b]);
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    const rect = canvasRef.current!.getBoundingClientRect();
    setStart([e.clientX - rect.left, e.clientY - rect.top]);
  };

  const handleMouseUp = (e: React.MouseEvent) => {
    if (!start) return;
    const rect = canvasRef.current!.getBoundingClientRect();
    const end = [e.clientX - rect.left, e.clientY - rect.top];
    onBoundsDraw(start, end);
    setStart(null);
  };

  return (
    <canvas
      ref={canvasRef}
      width={img?.width || 600}
      height={img?.height || 400}
      onClick={handleClick}
      onMouseDown={handleMouseDown}
      onMouseUp={handleMouseUp}
      style={{ border: '1px solid gray', cursor: 'crosshair' }}
    />
  );
}
