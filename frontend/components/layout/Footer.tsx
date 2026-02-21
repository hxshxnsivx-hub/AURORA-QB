export function Footer() {
  return (
    <footer className="border-t bg-gray-50 mt-auto">
      <div className="container mx-auto px-4 py-6">
        <div className="flex items-center justify-between text-sm text-gray-600">
          <p>&copy; 2024 AURORA Assess. All rights reserved.</p>
          <div className="flex gap-4">
            <a href="#" className="hover:text-gray-900">
              Documentation
            </a>
            <a href="#" className="hover:text-gray-900">
              Support
            </a>
            <a href="#" className="hover:text-gray-900">
              Privacy
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
}
